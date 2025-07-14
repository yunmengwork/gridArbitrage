from interface.trader import Trader
from interface.base_strategy import BaseStrategy
import numpy as np
import time
import json

# class Order:
# class GridOrder:


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

        # 时间参数
        self.time_tolerance = 3  # 时间容忍度，单位为秒

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
        self.cid_to_grid_pending_order = (
            {}
        )  # cid到网格挂单的映射, 用于跟踪网格挂单{"cid": grid_order}

        # trade
        self.trade_amount = 0.008  # 每次交易的数量

        # 设置杠杆
        self.leverage = 3

        # 订单管理
        self.pending_orders = {}  # 等待执行的订单列表

        # 仓位管理
        self.positions = {}  # 当前持仓信息

        #
        self.total_trade_num = 0  # 总交易次数

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
        for idx, level in enumerate(self.grid_levels):
            if level == self.base_price:
                continue
            order = {
                "price": level,
                "amount": self.trade_amount,  # 假设每个网格的交易量为0.008
                "side": "buy" if level < self.base_price else "sell",
                "grid_index": idx,  # 网格索引
            }
            self.grid_orders.append(order)

    def _remove_pending_order(self, cid):
        """从pending_orders挂单列表中移除指定的挂单,并且删除所对应的cid_to_grid_pending_order映射"""
        if cid in self.pending_orders:
            del self.pending_orders[cid]
        if cid in self.cid_to_grid_pending_order:
            del self.cid_to_grid_pending_order[cid]

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

        # ========================数据检查与状态更新========================

        # 检查BBO数据是否完整
        if any(self.bbo[symbol] is None for symbol in self.symbols):
            self.trader.tlog(
                tag="等待BBO数据接收",
                msg="BBO数据不完整，等待接收新数据",
                interval=2,
                level="WARN",
            )
            return

        # 如果数据时间戳异常，直接返回
        if (
            abs(self.bbo[self.spot]["timestamp"] - self.bbo[self.future]["timestamp"])
            > self.time_tolerance * 1000
        ):
            self.trader.tlog(
                tag="等待BBO数据接收",
                msg="BBO数据超过时间容忍度，等待接收新数据",
                interval=2,
                level="WARN",
            )
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
            # 如果指数移动平均线未初始化，直接使用当前middle价格
            self.trader.log(
                f"指数移动平均线未初始化，使用当前middle价格: {middle_price}初始化移动平均线 \
                \n使用{self.grid_num}作为上一次网格索引",
                level="INFO",
            )
            self.short_ewm = middle_price
            self.long_ewm = middle_price
            self.last_grid_index = self.grid_num  # 初始化网格索引
            return

        # 如果数据异常，直接返回
        if (
            abs(middle_price - self.short_ewm)
            > self.abnormal_threshold * self.short_ewm
        ):
            self.trader.tlog(
                tag="数据异常",
                msg=f"数据异常，跳过当前处理: {middle_price}",
                interval=2,
                level="WARN",
            )
            return

        # 更新指数移动平均线
        self._update_ewm(middle_price)

        # 如果网格级别未初始化，使用当前价格初始化
        if self.grid_levels is None:
            self.base_price = middle_price
            self._update_grid_levels(self.base_price)
            self._update_grid_orders()
            self.trader.log(
                f"初始化网格级别: {self.grid_levels}, 网格挂单: {self.grid_orders}",
                level="INFO",
            )

        # ========================模拟交易=========================

        # # 对于pending_orders中的订单
        # # 如果现在最新的bbo的卖一价小于当前pending_order中的买单的报价，模拟成交
        # # 如果现在最新的bbo的买一价大于当前pending_order中的卖单的报价，模拟成交
        # need_delete_pending_orders = []  # 需要删除的订单列表
        # for cid, order in self.pending_orders.items():
        #     if order["symbol"] != self.future:
        #         # 如果订单不是交割合约，则跳过
        #         continue
        #     if order["side"].lower() == "buy":
        #         if self.bbo[self.future]["ask_price"] <= order["price"]:
        #             # 模拟成交
        #             self.trader.log(
        #                 f"模拟成交: cid {cid}, {order}",
        #                 level="INFO",
        #             )
        #             need_delete_pending_orders.append(cid)
        #     elif order["side"].lower() == "sell":
        #         if self.bbo[self.future]["bid_price"] >= order["price"]:
        #             # 模拟成交
        #             self.trader.log(
        #                 f"模拟成交: cid {cid}, {order}",
        #                 level="INFO",
        #             )
        #             need_delete_pending_orders.append(cid)
        # # 删除已模拟成交的订单
        # for cid in need_delete_pending_orders:
        #     # 添加对应的网格挂单到网格挂单列表
        #     grid_order = self.cid_to_grid_pending_order.get(cid, None)
        #     if grid_order is not None:
        #         on_upper = grid_order["side"] == "buy"
        #         new_grid_order = {
        #             "price": (
        #                 grid_order["price"] + self.grid_interval
        #                 if on_upper
        #                 else grid_order["price"] - self.grid_interval
        #             ),
        #             "amount": grid_order["amount"],
        #             "side": "sell" if on_upper else "buy",
        #             "grid_index": (
        #                 grid_order["grid_index"] + 1
        #                 if on_upper
        #                 else grid_order["grid_index"] - 1
        #             ),
        #         }
        #         self.grid_orders.append(new_grid_order)
        #         self.trader.log(
        #             f"添加成交网格订单的对应网格挂单: {new_grid_order}",
        #             level="INFO",
        #         )
        #     self.trader.log(
        #         f"删除已模拟成交的订单: cid {cid}",
        #         level="INFO",
        #     )
        #     self._remove_pending_order(cid)

        # ========================订单检查=========================

        need_delete_pending_orders = []  # 需要删除的订单列表
        # 检查是否现在未成交的maker订单是否满足条件
        for cid, order in self.pending_orders.items():
            grid_order = self.cid_to_grid_pending_order.get(cid, None)
            if grid_order is None:
                self.trader.log(
                    f"订单 {cid} 找不到对应的网格挂单",
                    level="ERROR",
                )
                continue

            if grid_order["side"] == "buy" and grid_order["price"] >= self.buy_price:
                # 如果当前网格订单依旧满足条件，则不需要重新挂单
                # 检查订单是否为远期卖价一档
                if order["price"] == self.bbo[self.future]["ask_price"]:
                    continue
                else:
                    # 改单
                    order["price"] = self.bbo[self.future]["ask_price"]
                    self.trader.amend_order(0, order)
            elif (
                grid_order["side"] == "sell" and grid_order["price"] <= self.sell_price
            ):
                # 如果当前网格订单依旧满足条件，则不需要重新挂单
                # 检查订单是否为远期买价一档
                if order["price"] == self.bbo[self.future]["bid_price"]:
                    continue
                else:
                    # 改单
                    order["price"] = self.bbo[self.future]["bid_price"]
                    self.trader.amend_order(0, order)
            else:
                # 如果当前网格订单不满足条件，则取消订单
                self.trader.batch_cancel_order_by_id(0, client_order_ids=[cid])
                # 重新挂网格
                self.grid_orders.append(grid_order)
                # 添加到需要删除的订单列表
                need_delete_pending_orders.append(cid)

        for need_delete_pending_order in need_delete_pending_orders:
            self._remove_pending_order(need_delete_pending_order)

        # ========================检查是否需要修改网格=========================

        # 检查是否需要调整网格
        if abs(self.long_ewm - self.base_price) > self.grid_interval:
            # 撤掉所有挂单
            order_cids = list(self.pending_orders.keys())
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
                pass
            else:
                # 重新挂单
                self._update_grid_orders()

        # ========================检查是否需要开仓=============================

        # 计算当前网格索引
        grid_index = np.searchsorted(self.grid_levels, middle_price)
        buy_index = np.searchsorted(self.grid_levels, self.buy_price)
        sell_index = np.searchsorted(self.grid_levels, self.sell_price)

        # 检查是否需要执行交易
        if buy_index == self.last_grid_index and sell_index == self.last_grid_index:
            # 当前网格索引与上次相同，不需要执行交易
            self.last_grid_index = grid_index
            return

        for grid_order in self.grid_orders:
            if grid_order["side"] == "sell" and grid_order["price"] <= self.sell_price:
                # 执行卖出操作
                self._exec_grid_order(grid_order=grid_order)

            elif grid_order["side"] == "buy" and grid_order["price"] >= self.buy_price:
                # 执行买入操作
                self._exec_grid_order(grid_order=grid_order)
            else:
                continue

            # 从网格挂单中移除已执行的订单
            self.grid_orders.remove(grid_order)

        # 更新上次网格索引
        self.last_grid_index = grid_index

    def _exec_grid_order(self, grid_order):
        """执行网格订单
        grid_order: dict - 网格订单信息
        """
        # 注意这里拿到的价格是网格的价格，而不是挂单的价格
        # 执行交易逻辑
        # 交割合约挂单
        # 交割合约挂单方向与网格方向相反
        grid_price = grid_order["price"]
        grid_amount = grid_order["amount"]
        grid_side = grid_order["side"]
        grid_index = grid_order["grid_index"]
        actual_side = "buy" if grid_side == "sell" else "sell"
        cid = self.trader.create_cid(self.cex_configs[0]["exchange"])
        order = {
            "cid": cid,
            "symbol": self.future,
            "order_type": "Limit",
            "side": actual_side.capitalize(),
            "amount": grid_amount,
            "price": (
                self.bbo[self.future]["bid_price"]
                if actual_side == "Buy"
                else self.bbo[self.future]["ask_price"]
            ),
        }
        # 执行挂单
        order_result = self.trader.place_order(0, order)
        # 记录订单信息
        self.cid_to_grid_pending_order[cid] = {
            "price": grid_price,
            "amount": grid_amount,
            "side": grid_side,
            "grid_index": grid_index,
        }
        self.pending_orders[cid] = order

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
            # 删除order
            del self.cid_to_grid_order[order["cid"]]
            del self.orders[order["cid"]]

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
