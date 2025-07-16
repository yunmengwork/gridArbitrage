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

        # has_account: bool = False  # 是否有账户信息
        self.has_account = True  # 是否有账户信息

        # 交易币种
        self.pairs = self.config.get("pairs", {})
        if not self.pairs:
            raise ValueError("策略配置中未指定交易对，请检查配置文件。")
        self.spot = self.pairs.get("spot", "")
        self.future = self.pairs.get("future", "")
        self.placeFutureSymbol = self.future.replace("_25", "-2025")  # 交割合约符号
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

        # sync
        self.sync = False  # 是否同步执行

        # 订单管理
        self.pending_orders = {}  # 等待执行的订单列表

        # 仓位管理
        self.positions = {}  # 当前持仓信息

        #
        self.total_trade_num = 0  # 总交易次数

        # Lock
        self.pending_orders_lock = False  # 锁，防止多线程冲突
        self.grid_orders_lock = False  # 锁，防止多线程冲突

        self.execMaxNum = 3  # 是否执行交易
        self.execNum = 0  # 当前执行次数

    def wait_lock_release(self, lock_name, msg=None, timeout=5):
        """等待锁释放"""
        start_time = time.time()
        if getattr(self, lock_name):
            self.trader.log(
                f"等待锁 {lock_name} 释放. {msg if msg else ''}",
                level="WARN",
            )
            while getattr(self, lock_name):
                time.sleep(0.001)
                if time.time() - start_time > timeout:
                    self.trader.log(f"锁 {lock_name} 超时释放!", level="ERROR")
                    setattr(self, lock_name, False)  # 强制释放
                    break
            self.trader.log(
                f"锁 {lock_name} 已释放",
                level="INFO",
            )

    def name(self):
        """返回策略名称"""
        return "期限价差套利策略"

    def subscribes(self):
        subs = [
            {
                "account_id": 0,
                "sub": {
                    "SubscribeWs": [
                        {"Bbo": self.symbols},  # 订阅最优买卖价
                    ]
                },
            }
        ]
        if self.has_account:
            subs.append(
                {
                    "account_id": 0,
                    "sub": {
                        "SubscribeWs": [
                            {"Order": [self.spot]},  # 订阅订单信息
                            {"Position": [self.spot]},  # 订阅持仓信息
                        ]
                    },
                }
            )
            subs.append(
                {
                    "account_id": 1,
                    "sub": {
                        "SubscribeWs": [
                            {"Order": [self.placeFutureSymbol]},  # 订阅订单信息
                            {"Position": [self.placeFutureSymbol]},  # 订阅持仓信息
                        ]
                    },
                }
            )

        return subs

    def start(self):
        """策略启动函数"""
        # 设置杠杆
        # for symbol in self.symbols:
        #     self.trader.set_leverage(symbol, self.leverage)
        pass

    def on_bbo(self, exchange, bbo):
        time.sleep(1)  # 确保数据处理不会过快
        if self.execNum < self.execMaxNum:
            cid = self.trader.create_cid("BinanceSwap")  # 创建一个唯一的cid
            order = {
                "cid": cid,
                "symbol": self.spot,
                "side": "Buy",
                "order_type": "Limit",
                "amount": 0.008,  # 设置一个初始的买入数量
                "time_in_force": "PostOnly",
                "price": 2900,
            }
            send_time = int(time.time() * 1000)
            self.trader.place_order(0, order, sync=False)  # 异步下单
            order["send_time"] = send_time  # 添加发送时间戳到订单信息
            self.pending_orders[cid] = order
            self.execNum += 1

    def on_order(self, exchange, order):
        """处理订单数据
        exchange: str - 交易所名称
        order: dict - 订单数据
        """
        cid = order.get("cid", None)
        self.trader.log(
            f"收到订单数据: {json.dumps(order, indent=2)}",
            level="INFO",
        )
        if cid in self.pending_orders:
            # 如果订单在待处理列表中，更新订单状态
            time_cost = order["timestamp"] - self.pending_orders[cid]["send_time"]
            self.trader.log(
                f"订单 {cid} 从发出到被服务器接受耗时: {time_cost} ms",
                level="INFO",
            )
