from interface.trader import Trader
from interface.base_strategy import BaseStrategy
import numpy as np
import time
import json


# 类名必须为Strategy
class Strategy(BaseStrategy):
    def __init__(self, cex_configs, dex_configs, config, trader: Trader):
        self.cex_configs = cex_configs  # 中心化交易所配置
        self.dex_configs = dex_configs  # 去中心化交易所配置
        self.config = config  # 策略配置
        self.trader = trader  # 交易执行器
        self.stop_flag = False  # 停止标志

        # 交易币种
        self.pairs = self.config.get("pairs", {})
        if not self.pairs:
            raise ValueError("策略配置中未指定交易对，请检查配置文件。")
        self.spot = self.pairs.get("spot", "")
        self.future = self.pairs.get("future", "")
        self.symbols = [symbol for symbol in self.pairs.values()]

        # 记录最新的市场数据
        self.bbo = {symbol: None for symbol in self.symbols}

        # 辅助变量
        self.short_span = 3 * 60 * 60 * 100
        self.long_span = 36 * 60 * 60 * 100
        self.short_ewm = None
        self.long_ewm = None
        self.buy_price = None
        self.sell_price = None

        # 异常阈值
        self.abnormal_threshold = 0.003

        # 网格
        self.grid_interval = self.config.get("grid_config", {}).get(
            "grid_interval", 0.0007
        )
        self.grid_num = self.config.get("grid_config", {}).get("grid_num", 4)
        self.base_price = None
        self.grid_levels = None
        self.last_grid_index = None
        # 网格挂单
        self.grid_orders = []  # 挂单列表
        self.reorder_threshold = (
            0.5  # 网格重新挂单的阈值, 需要更新网格是base_price在网格中部50%以内
        )
        self.cid_to_grid_order = (
            {}
        )  # cid到网格订单的映射, 用于跟踪网格订单{"cid": grid_order}

        # trade
        self.trade_amount = 0.008  # 每次交易的数量

        # 设置杠杆
        self.leverage = 3

        # 订单管理
        self.orders = {}  # 当前订单信息

        # 仓位管理
        self.positions = {}  # 当前持仓信息

    def name(self):
        """返回策略名称"""
        return "期限价差套利策略"

    def subscribes(self):
        subs = [
            # {
            #     "account_id": 0,
            #     "sub": {
            #         "SubscribeWs": [
            #             {"Bbo": self.symbols},  # 订阅最优买卖价
            #         ]
            #     },
            # }
        ]

        return subs

    def start(self):
        """策略启动函数"""
        # 设置杠杆
        # for symbol in self.symbols:
        #     self.trader.set_leverage(symbol, self.leverage)
        pass

    def __process_symbol(self, symbol):
        """对symbol进行调整，对于每一个回调数据，都需要处理"""
        if "-" in symbol:
            return symbol.replace("-20", "_")
        return symbol

    def _update_ewm(self, price):
        """更新指数移动平均线"""
        if self.short_ewm is None:
            self.short_ewm = price
        else:
            self.short_ewm = (
                (self.short_span - 1) * self.short_ewm + price
            ) / self.short_span

        if self.long_ewm is None:
            self.long_ewm = price
        else:
            self.long_ewm = (
                (self.long_span - 1) * self.long_ewm + price
            ) / self.long_span

    def _update_grid_levels(self, base_price):
        """更新网格级别"""
        self.grid_levels = []
        for i in range(-self.grid_num, self.grid_num + 1):
            level_price = base_price + i * self.grid_interval
            self.grid_levels.append(level_price)

    def _update_grid_orders(self):
        """更新挂单列表, 确保挂单与网格级别一致"""
        self.grid_orders = []
        for level in self.grid_levels:
            if level == self.base_price:
                continue
            order = {
                "price": level,
                "amount": self.trade_amount,  # 假设每个网格的交易量为0.008
                "side": "buy" if level < self.base_price else "sell",
            }
            self.grid_orders.append(order)

    def on_bbo(self, exchange, bbo):
        """处理BBO数据
        exchange: str - 交易所名称
        bbo: dict - BBO数据
        """
        # 先对symbol进行处理
        bbo["symbol"] = self.__process_symbol(bbo["symbol"])

        # 更新最新的BBO数据
        symbol = bbo["symbol"]
        self.bbo[symbol] = bbo

        # 检查BBO数据是否完整
        print(self.bbo)
        if any(self.bbo[symbol] is None for symbol in self.symbols):
            print("等待BBO数据...")
            return

        # 计算买卖数据
        self.buy_price = (
            self.bbo[self.spot]["ask_price"] / self.bbo[self.future]["ask_price"]
        )
        self.sell_price = (
            self.bbo[self.spot]["bid_price"] / self.bbo[self.future]["bid_price"]
        )
        middle_price = (self.buy_price + self.sell_price) / 2

        #
        if self.short_ewm is None or self.long_ewm is None:
            # 如果指数移动平均线未初始化，直接使用当前价格
            self.short_ewm = middle_price
            self.long_ewm = middle_price
            self.last_grid_index = self.grid_num  # 初始化网格索引
            return

        # 如果数据异常，直接返回
        if (
            abs(middle_price - self.short_ewm)
            > self.abnormal_threshold * self.short_ewm
        ):
            print(f"数据异常，跳过当前处理: {middle_price}")
            return

        # 更新指数移动平均线
        self._update_ewm(middle_price)

        # 如果网格级别未初始化，使用当前价格初始化
        if self.grid_levels is None:
            self.base_price = middle_price
            self._update_grid_levels(self.base_price)
            self._update_grid_orders()

        # 计算当前网格索引
        grid_index = np.searchsorted(self.grid_levels, self.base_price)

        # 检查是否现在未成交的maker订单是否满足条件

        # 检查是否需要执行交易
        if grid_index == self.last_grid_index:
            # 当前网格索引与上次相同，不需要执行交易
            self.last_grid_index = grid_index
            return

        elif grid_index > self.last_grid_index:
            # 当前网格索引大于上次，说明价格上涨, 需要执行卖出操作
            for order in self.grid_orders:
                if order["side"] == "sell" and order["price"] <= self.sell_price:
                    # 执行卖出操作
                    self._exec_grid_order(
                        price=order["price"],
                        amount=order["amount"],
                        side=order["side"],
                    )

        elif grid_index < self.last_grid_index:
            # 当前网格索引小于上次，说明价格下跌
            for order in self.grid_orders:
                if order["side"] == "buy" and order["price"] >= self.buy_price:
                    # 执行买入操作
                    self._exec_grid_order(
                        price=order["price"],
                        amount=order["amount"],
                        side=order["side"],
                    )

        # 更新上次网格索引
        self.last_grid_index = grid_index

        # 检查是否需要调整网格
        if abs(self.long_ewm - self.base_price) > self.grid_interval:
            # 撤掉所有挂单
            order_cids = list(self.orders.keys())
            if order_cids:
                self.trader.batch_cancel_order_by_id(0, client_order_ids=order_cids)

            # 市价平掉持有仓位
            self._market_close_all()

            # 更新网格与基准价格
            self.base_price = self.long_ewm
            self._update_grid_levels(self.base_price)

            # 清空当前网格挂单
            self.grid_orders = []
            # 检查是否需要重新挂单
            if (
                self.base_price
                > self.reorder_threshold * self.grid_interval
                + self.grid_levels[self.grid_num]
                or self.base_price
                < self.grid_levels[self.grid_num]
                - self.reorder_threshold * self.grid_interval
            ):
                # 超出阈值，不挂单
                return

            # 重新挂单
            self._update_grid_orders()

    def _exec_grid_order(self, price, amount, side):
        """执行网格订单
        id: str - 跟踪网格订单ID
        price: float - 订单价格
        amount: float - 订单数量
        side: str - 订单方向，'buy' 或 'sell'
        """
        # 执行交易逻辑
        # 交割合约挂单
        # 交割合约挂单方向与网格方向相反
        actual_side = "buy" if side == "sell" else "sell"
        cid = self.trader.create_cid(self.cex_configs[0]["exchange"])
        order = {
            "cid": cid,
            "symbol": self.future,
            "order_type": "Limit",
            "side": actual_side.capitalize(),
            "amount": amount,
            "price": price,
        }
        # 执行挂单
        order_result = self.trader.place_order(0, order)
        print(order_result)
        # 记录订单信息
        self.cid_to_grid_order[cid] = {
            "price": price,
            "amount": amount,
            "side": side,
        }
        self.orders[cid] = order

    def _market_close_all(self):
        """平掉所有仓位"""
        for symbol in self.symbols:
            # 平掉所有仓位
            position = self.positions.get(symbol, None)
            if position:
                # 执行平仓操作
                if position["amount"] == 0:
                    continue
                if position["side"].lower() == "long":
                    order = {
                        "symbol": symbol,
                        "order_type": "Market",
                        "side": "Sell",
                        "amount": position["amount"],
                        "price": None,  # 市价平仓
                    }
                    self.trader.place_order(0, order)
                elif position["side"].lower() == "short":
                    order = {
                        "symbol": symbol,
                        "order_type": "Market",
                        "side": "Buy",
                        "amount": position["amount"],
                        "price": None,  # 市价平仓
                    }
                    self.trader.place_order(0, order)
                # 清除持仓信息
                self.positions[symbol] = None

    def on_order(self, exchange, order):
        """处理订单数据
        exchange: str - 交易所名称
        order: dict - 订单数据
        """
        # 先对symbol进行处理
        order["symbol"] = self.__process_symbol(order["symbol"])

        # 一旦交割合约成交，使用永续/现货市价对冲
        if order["symbol"] == self.future and order["status"] == "Filled":
            side = "Buy" if order["side"] == "Sell" else "Sell"
            amount = order["filled_amount"]
            self.exec_hedge(self.spot, side, amount)
            # 网格订单成交，处理
            grid_order = self.cid_to_grid_order.get(order["cid"], None)
            if grid_order:
                # 从网格订单中移除
                self.grid_orders.remove(grid_order)
                # 重新挂网格
                new_grid_order = {}
                side = "buy" if grid_order["side"] == "sell" else "sell"
                new_grid_order["price"] = (
                    grid_order["price"] - self.grid_interval
                    if side == "buy"
                    else grid_order["price"] + self.grid_interval
                )
                new_grid_order["amount"] = grid_order["amount"]
                new_grid_order["side"] = side
                self.grid_orders.append(new_grid_order)

    def exec_hedge(self, symbol, side, amount):
        """执行对冲操作, 市价对冲
        symbol: str - 交易对
        side: str - 方向，'buy' 或 'sell'
        amount: float - 数量
        """
        order = {
            "symbol": symbol,
            "order_type": "Market",
            "side": side.capitalize(),
            "amount": amount,
            "price": None,  # 市价对冲
        }
        # 执行对冲操作
        order_result = self.trader.place_order(0, order)
        print(f"对冲订单执行结果: {order_result}")
