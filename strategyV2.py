from interface.trader import Trader
from interface.base_strategy import BaseStrategy
import numpy as np
import time
import json
import csv
import os
from collections import OrderedDict

# class Order:
# class GridOrder:


class LatencyStats:
    """延迟统计类"""

    def __init__(self, max_capacity=1000, output_file=None, batch_size=10):
        self.max_capacity = max_capacity  # 每个orderType的最大容量
        self.output_file = output_file  # CSV输出文件路径
        self.batch_size = batch_size  # 批量保存的数据量
        self.order_delay_stats = {
            "place_order": OrderedDict(),  # 使用OrderedDict维护插入顺序
            "cancel_order": OrderedDict(),
            "amend_order": OrderedDict(),
        }

        # 批量保存相关
        self.pending_data = []  # 待保存的数据缓存
        self.file_initialized = False  # 文件是否已初始化

    def _create_stats_cid(self, order):
        """创建cid，使用下划线合并cid与price*100"""
        cid = order["cid"]
        price = order["price"]
        return f"{cid}_{int(price * 100)}"

    def _ensure_capacity(self, order_type):
        """确保指定orderType不超过最大容量，超过时删除最早的元素"""
        if len(self.order_delay_stats[order_type]) >= self.max_capacity:
            # 删除最早添加的元素
            self.order_delay_stats[order_type].popitem(last=False)

    def _init_csv_file(self):
        """初始化CSV文件，写入表头"""
        if not self.output_file or self.file_initialized:
            return

        # 确保目录存在
        os.makedirs(os.path.dirname(self.output_file), exist_ok=True)

        # 写入CSV表头
        with open(self.output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "stats_cid",
                    "order_type",
                    "server_receive_time",
                    "local_place_time",
                    "latency_ms",
                ]
            )

        self.file_initialized = True

    def _save_batch_data(self):
        """批量保存数据到CSV文件"""
        if not self.output_file or not self.pending_data:
            return

        # 初始化文件（如果需要）
        self._init_csv_file()

        # 追加数据到CSV文件
        with open(self.output_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerows(self.pending_data)

        # 清空缓存
        self.pending_data = []

    def _add_to_batch(
        self, stats_cid, order_type, server_receive_time, local_place_time, latency
    ):
        """添加数据到批量缓存"""
        if not self.output_file:
            return

        # 添加到缓存
        self.pending_data.append(
            [stats_cid, order_type, server_receive_time, local_place_time, latency]
        )

        # 检查是否达到批量保存阈值
        if len(self.pending_data) >= self.batch_size:
            self._save_batch_data()

    def add_when_submit(self, order, order_type):
        """添加下单延迟"""
        stats_cid = self._create_stats_cid(order)

        # 在添加新元素前检查容量
        self._ensure_capacity(order_type)

        self.order_delay_stats[order_type][stats_cid] = {
            "local_place_time": time.time() * 1000,
            "server_receive_time": None,
            "status": "pending",
        }

    def add_when_recive(self, order, order_type):
        """添加接收时间,并返回延迟"""
        stats_cid = self._create_stats_cid(order)
        if stats_cid in self.order_delay_stats[order_type]:
            self.order_delay_stats[order_type][stats_cid]["server_receive_time"] = (
                order["timestamp"]
            )
            self.order_delay_stats[order_type][stats_cid]["status"] = "done"
            local_place_time = self.order_delay_stats[order_type][stats_cid][
                "local_place_time"
            ]
            server_receive_time = self.order_delay_stats[order_type][stats_cid][
                "server_receive_time"
            ]

            latency = server_receive_time - local_place_time

            # 保存数据到批量缓存
            self._add_to_batch(
                stats_cid, order_type, server_receive_time, local_place_time, latency
            )

            return latency
        return None

    def flush_pending_data(self):
        """强制保存所有待保存的数据"""
        if self.pending_data:
            self._save_batch_data()


class SlippageStats:
    """滑点统计类"""

    def __init__(self, max_capacity=1000, output_file=None, batch_size=4):
        self.max_capacity = max_capacity  # 每个orderType的最大容量
        self.output_file = output_file  # CSV输出文件路径
        self.batch_size = batch_size  # 批量保存的数据量
        self.order_slippage_stats = {
            "hedge_order": OrderedDict(),  # 对冲订单滑点
            "grid_order": OrderedDict(),  # 网格订单滑点
        }

        # 批量保存相关
        self.pending_data = []  # 待保存的数据缓存
        self.file_initialized = False  # 文件是否已初始化

    def _ensure_capacity(self, order_type):
        """确保指定orderType不超过最大容量，超过时删除最早的元素"""
        if len(self.order_slippage_stats[order_type]) >= self.max_capacity:
            # 删除最早添加的元素
            self.order_slippage_stats[order_type].popitem(last=False)

    def _init_csv_file(self):
        """初始化CSV文件，写入表头"""
        if not self.output_file or self.file_initialized:
            return

        # 确保目录存在
        os.makedirs(os.path.dirname(self.output_file), exist_ok=True)

        # 写入CSV表头
        with open(self.output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "stats_cid",
                    "order_type",
                    "expected_price",
                    "actual_price",
                    "slippage_abs",
                    "slippage_bps",
                    "side",
                    "amount",
                    "fill_time",
                ]
            )

        self.file_initialized = True

    def _save_batch_data(self):
        """批量保存数据到CSV文件"""
        if not self.output_file or not self.pending_data:
            return

        # 初始化文件（如果需要）
        self._init_csv_file()

        # 追加数据到CSV文件
        with open(self.output_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerows(self.pending_data)

        # 清空缓存
        self.pending_data = []

    def _add_to_batch(
        self,
        cid,
        order_type,
        expected_price,
        actual_price,
        slippage_abs,
        slippage_bps,
        side,
        amount,
        fill_time,
    ):
        """添加数据到批量缓存"""
        if not self.output_file:
            return

        # 添加到缓存
        self.pending_data.append(
            [
                cid,
                order_type,
                expected_price,
                actual_price,
                slippage_abs,
                slippage_bps,
                side,
                amount,
                fill_time,
            ]
        )

        # 检查是否达到批量保存阈值
        if len(self.pending_data) >= self.batch_size:
            self._save_batch_data()

    def add_when_place(self, order, order_type, expected_price):
        """添加下单时的期望价格"""
        cid = order["cid"]

        # 在添加新元素前检查容量
        self._ensure_capacity(order_type)

        self.order_slippage_stats[order_type][cid] = {
            "expected_price": expected_price,
            "order_info": {
                "side": order.get("side", ""),
                "amount": order.get("amount", 0),
                "price": order.get("price", 0),
            },
            "status": "pending",
        }

    def add_when_filled(self, order, order_type):
        """订单成交时计算滑点"""
        cid = order["cid"]

        if cid in self.order_slippage_stats[order_type]:
            stats_data = self.order_slippage_stats[order_type][cid]
            expected_price = stats_data["expected_price"]
            actual_price = order.get("filled_avg_price", order.get("price", 0))
            side = order.get("side", "").lower()
            amount = order.get("filled", 0)
            fill_time = order.get("timestamp", None)

            # 计算滑点
            if side == "buy":
                # 买入时，实际价格高于期望价格为正滑点
                slippage_abs = actual_price - expected_price
            else:
                # 卖出时，实际价格低于期望价格为正滑点
                slippage_abs = expected_price - actual_price

            # 计算基点滑点 (basis points)
            slippage_bps = (
                (slippage_abs / expected_price) * 10000 if expected_price > 0 else 0
            )

            # 保存数据到批量缓存
            self._add_to_batch(
                cid,
                order_type,
                expected_price,
                actual_price,
                slippage_abs,
                slippage_bps,
                side,
                amount,
                fill_time,
            )

            # 标记为已完成
            stats_data["status"] = "filled"

            return slippage_abs, slippage_bps

        return None, None

    def flush_pending_data(self):
        """强制保存所有待保存的数据"""
        if self.pending_data:
            self._save_batch_data()


class dealPriceStats:
    def __init__(self, output_file=None, batch_size=4):
        self.output_file = output_file  # CSV输出文件路径
        self.batch_size = batch_size  # 批量保存的数据量
        self.grid_order_stats = (
            {}
        )  # 网格订单成交价格统计{<hedge_order_cid>: {"grid_order": grid_order, "hedge_order": hedge_order, "future_deal_price": future_deal_price}}

        # 批量保存相关
        self.pending_data = []  # 待保存的数据缓存
        self.file_initialized = False  # 文件是否已初始化

    def _init_csv_file(self):
        """初始化CSV文件，写入表头"""
        if not self.output_file or self.file_initialized:
            return

        # 确保目录存在
        os.makedirs(os.path.dirname(self.output_file), exist_ok=True)

        # 写入CSV表头
        with open(self.output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "hedge_order_cid",
                    "grid_side",
                    "grid_expected_price",
                    "grid_actual_price",
                    "grid_slippage",
                    "future_deal_price",
                    "hedge_deal_price",
                    "grid_amount",
                    "deal_time",
                ]
            )

        self.file_initialized = True

    def _save_batch_data(self):
        """批量保存数据到CSV文件"""
        if not self.output_file or not self.pending_data:
            return

        # 初始化文件（如果需要）
        self._init_csv_file()

        # 追加数据到CSV文件
        with open(self.output_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerows(self.pending_data)

        # 清空缓存
        self.pending_data = []

    def _add_to_batch(
        self,
        hedge_order_cid,
        grid_side,
        grid_expected_price,
        grid_actual_price,
        grid_slippage,
        future_deal_price,
        hedge_deal_price,
        grid_amount,
        deal_time,
    ):
        """添加数据到批量缓存"""
        if not self.output_file:
            return

        # 添加到缓存
        self.pending_data.append(
            [
                hedge_order_cid,
                grid_side,
                grid_expected_price,
                grid_actual_price,
                grid_slippage,
                future_deal_price,
                hedge_deal_price,
                grid_amount,
                deal_time,
            ]
        )

        # 检查是否达到批量保存阈值
        if len(self.pending_data) >= self.batch_size:
            self._save_batch_data()

    def add_deal_grid_order(self, hedge_order_cid, grid_order, future_deal_price):
        """添加成交的网格订单价格"""
        self.grid_order_stats[hedge_order_cid] = {
            "grid_order": grid_order,
            "hedge_order": None,
            "future_deal_price": future_deal_price,
        }

    def add_deal_hedge_order(self, hedge_order):
        """添加成交的对冲订单价格"""
        hedge_order_cid = hedge_order["cid"]
        if hedge_order_cid not in self.grid_order_stats:
            return None
        self.grid_order_stats[hedge_order_cid]["hedge_order"] = hedge_order

        hedge_deal_price = hedge_order.get(
            "filled_avg_price", hedge_order.get("price", 0)
        )
        future_deal_price = self.grid_order_stats[hedge_order_cid]["future_deal_price"]
        grid_deal_price = hedge_deal_price / future_deal_price

        # 计算网格滑点
        grid_order = self.grid_order_stats[hedge_order_cid]["grid_order"]
        side = grid_order["side"]
        expected_price = grid_order["price"]
        if side == "buy":
            grid_slippage = grid_deal_price - expected_price
        else:
            grid_slippage = expected_price - grid_deal_price

        # 保存数据到批量缓存
        self._add_to_batch(
            hedge_order_cid,
            side,
            expected_price,
            grid_deal_price,
            grid_slippage,
            future_deal_price,
            hedge_deal_price,
            hedge_order.get("filled", 0),
            hedge_order.get("timestamp", None),
        )

        return grid_deal_price, grid_slippage

    def flush_pending_data(self):
        """强制保存所有待保存的数据"""
        if self.pending_data:
            self._save_batch_data()


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
        self.time_tolerance = 5  # 时间容忍度，单位为秒

        # 辅助变量
        self.short_span = 3 * 60 * 60 * 100
        self.long_span = 36 * 60 * 60 * 100
        self.short_ewm = None
        self.long_ewm = None

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
        self.grid_orders = {}  # 挂单列表，<grid_index, grid_order>
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
        self.continuous_open_signal_lock = False  # 锁，防止多线程冲突

        # 持续开仓信号，表明是稳定区间而不是大波动
        self.continuous_open_signal_min_num = 30  # 连续开仓信号最小数量
        self.continuous_open_signal = {}  # <grid_index, count>

        # 对延迟进行统计，下单，撤单，取消订单延迟
        self.order_delay_stats = LatencyStats(
            output_file=f"./stats/{int(time.time()*1000)}_order_delay.csv"
        )  # 延迟统计对象

        # 对滑点进行统计
        self.slippage_stats = SlippageStats(
            output_file=f"./stats/{int(time.time()*1000)}_slippage.csv"
        )  # 滑点统计对象

        # 对网格成交价格进行统计
        self.deal_price_stats = dealPriceStats(
            output_file=f"./stats/{int(time.time()*1000)}_deal_price.csv"
        )  # 成交价格统计对象

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

    def _reset_continuous_open_signal(self):
        """重置连续开仓信号"""
        self.wait_lock_release("continuous_open_signal_lock", "重置连续开仓信号")
        self.continuous_open_signal_lock = True  # 设置锁，防止多线程
        self.continuous_open_signal = {}
        for i in range(2 * self.grid_num + 1):
            self.continuous_open_signal[i] = 0
        self.continuous_open_signal_lock = False

    def _update_grid_levels(self, base_price):
        """更新网格级别"""
        self.grid_levels = []
        for i in range(-self.grid_num, self.grid_num + 1):
            level_price = base_price + i * self.grid_interval
            self.grid_levels.append(level_price)

    def _update_grid_orders(self):
        """更新挂单列表, 确保挂单与网格级别一致"""
        self.wait_lock_release("grid_orders_lock", "更新网格挂单列表")
        self.grid_orders_lock = True  # 设置锁，防止多线程冲突
        self.grid_orders = {}
        for idx, level in enumerate(self.grid_levels):
            if level == self.base_price:
                continue
            order = {
                "price": level,
                "amount": self.trade_amount,  # 假设每个网格的交易量为0.008
                "side": "buy" if level < self.base_price else "sell",
                "grid_index": idx,  # 网格索引
            }
            self.grid_orders[idx] = order  # 使用网格索引作为键
        self.grid_orders_lock = False  # 释放锁

    def _remove_pending_order(self, cid):
        """从pending_orders挂单列表中移除指定的挂单,并且删除所对应的cid_to_grid_pending_order映射"""
        self.wait_lock_release("pending_orders_lock", "移除挂单")
        self.pending_orders_lock = True  # 设置锁，防止多线程冲突
        if cid in self.pending_orders:
            del self.pending_orders[cid]
        if cid in self.cid_to_grid_pending_order:
            del self.cid_to_grid_pending_order[cid]
        self.pending_orders_lock = False  # 释放锁

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

        # 使用bbo副本运行
        bbo_copy = self.bbo.copy()

        # 计算买卖数据
        buy_price = (
            bbo_copy[self.spot]["ask_price"] / bbo_copy[self.future]["ask_price"]
        )
        sell_price = (
            bbo_copy[self.spot]["bid_price"] / bbo_copy[self.future]["bid_price"]
        )
        middle_price = (buy_price + sell_price) / 2

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
            self._reset_continuous_open_signal()  # 重置连续开仓信号
            self.trader.log(
                f"初始化网格级别: {self.grid_levels}, 网格挂单: {self.grid_orders}",
                level="INFO",
            )

        # ========================订单检查=========================

        # 这里不使用锁是因为可以接受同时有多个线程在执行订单检查
        # 检查是否现在未成交的maker订单是否满足条件
        pending_orders_copy = self.pending_orders.copy()
        for cid, order in pending_orders_copy.items():
            grid_order = self.cid_to_grid_pending_order.get(cid, None)
            if grid_order is None:
                self.trader.log(
                    f"订单 {cid} 找不到对应的网格挂单",
                    level="ERROR",
                )
                continue

            if grid_order["side"] == "buy" and grid_order["price"] >= buy_price:
                grid_order["maker_price"] = (
                    np.round(bbo_copy[self.future]["ask_price"] - 0.1, 2)
                    if grid_order["maker_price"] > bbo_copy[self.future]["ask_price"]
                    else grid_order["maker_price"]
                )  # 确保自己是最前面的订单
                grid_order["taker_price"] = bbo_copy[self.spot]["ask_price"]
                # 如果当前网格订单依旧满足条件，则不需要重新挂单
                # 检查订单是否为远期卖价一档
                if order["price"] == grid_order["maker_price"]:
                    continue
                else:
                    # 改单
                    last_price = order["price"]
                    order["price"] = (
                        grid_order["maker_price"]
                        if grid_order["maker_price"]
                        > bbo_copy[self.future]["bid_price"]
                        else bbo_copy[self.future]["ask_price"]
                    )
                    # 统计订单延迟
                    self.order_delay_stats.add_when_submit(order, "amend_order")
                    # 统计滑点
                    self.slippage_stats.add_when_place(
                        order, "grid_order", grid_order["maker_price"]
                    )
                    res = self.trader.amend_order(1, order, sync=self.sync)
                    self.trader.tlog(
                        tag="改单",
                        msg=f"订单 {cid}, 方向 {grid_order['side']} 原价 {last_price} -> 新价 {order['price']} \
                            \n改单结果: {res}",
                        level="INFO",
                        interval=1,
                    )
            elif grid_order["side"] == "sell" and grid_order["price"] <= sell_price:
                grid_order["maker_price"] = (
                    np.round(bbo_copy[self.future]["bid_price"] + 0.1, 2)
                    if grid_order["maker_price"] < bbo_copy[self.future]["bid_price"]
                    else grid_order["maker_price"]
                )  # 确保自己是最前面的订单
                grid_order["taker_price"] = bbo_copy[self.spot]["bid_price"]
                # 如果当前网格订单依旧满足条件，则不需要重新挂单
                # 检查订单是否为远期买价一档
                if order["price"] == grid_order["maker_price"]:
                    continue
                else:
                    # 改单
                    last_price = order["price"]
                    order["price"] = (
                        grid_order["maker_price"]
                        if grid_order["maker_price"]
                        < bbo_copy[self.future]["ask_price"]
                        else bbo_copy[self.future]["bid_price"]
                    )
                    # 统计订单延迟
                    self.order_delay_stats.add_when_submit(order, "amend_order")
                    # 统计滑点
                    self.slippage_stats.add_when_place(
                        order, "grid_order", grid_order["maker_price"]
                    )
                    res = self.trader.amend_order(1, order, sync=self.sync)
                    self.trader.tlog(
                        tag="改单",
                        msg=f"订单 {cid}, 方向 {grid_order['side']} 原价 {last_price} -> 新价 {order['price']} \
                            \n改单结果: {res}",
                        level="INFO",
                        interval=1,
                    )
            else:
                # 取消订单
                # 统计订单延迟
                self.order_delay_stats.add_when_submit(order, "cancel_order")
                res = self.trader.batch_cancel_order_by_id(
                    1,
                    client_order_ids=[cid],
                    symbol=self.placeFutureSymbol,
                    sync=self.sync,
                )
                self.trader.tlog(
                    tag="取消订单",
                    msg=f"订单 {cid} 不满足条件，取消订单 \
                        \n取消结果: {res}",
                    level="INFO",
                    interval=1,
                )
                self.wait_lock_release("pending_orders_lock", "检查未成交挂单")
                self.pending_orders_lock = True  # 设置锁，防止多线程冲突
                if cid in self.pending_orders:
                    del self.pending_orders[cid]
                self.pending_orders_lock = False  # 释放锁

            # 按理来说取消挂单就需要将网格挂单重新挂单，也就是添加回网格挂单列表
            # 但是我们希望在收到订单回执时知道某一订单对应的是哪个网格挂单
            # 所以这里不需要将网格挂单重新添加到网格挂单列表，重新挂单的操作在接受到订单取消时执行
            # 所以这里只删除self.pending_orders，取消的订单不需要再做订单检查

        # ========================检查是否需要修改网格=========================

        # 检查是否需要调整网格
        if abs(self.long_ewm - self.base_price) > self.grid_interval:
            self.trader.tlog(
                tag="网格调整",
                msg=f"基准价格 {self.base_price} 与长期均线 {self.long_ewm} 差异超过阈值，调整网格",
                level="INFO",
            )
            # 撤掉所有挂单
            order_cids = list(self.pending_orders.keys())
            if order_cids:
                self.trader.batch_cancel_order_by_id(0, client_order_ids=order_cids)

            # 市价平掉持有仓位
            self._market_close_all()

            # 更新网格与基准价格
            self.base_price = self.long_ewm
            self._update_grid_levels(self.base_price)

            # 重置连续开仓信号
            self._reset_continuous_open_signal()

            # 清空当前网格挂单
            self.grid_orders = {}
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
                self.trader.tlog(
                    tag="网格调整",
                    msg=f"基准价格 {self.base_price} 超出阈值，不重新挂单",
                    level="INFO",
                )
                pass
            else:
                # 重新挂单
                self._update_grid_orders()
                self.trader.tlog(
                    tag="网格调整",
                    msg=f"重新挂单: {self.grid_orders}",
                    level="INFO",
                )

        # ========================检查是否需要开仓=============================

        # 计算当前网格索引
        grid_index = np.searchsorted(self.grid_levels, middle_price)
        buy_index = np.searchsorted(self.grid_levels, buy_price)
        sell_index = np.searchsorted(self.grid_levels, sell_price)

        # 检查是否需要执行交易
        if buy_index == self.last_grid_index and sell_index == self.last_grid_index:
            # 当前网格索引与上次相同，不需要执行交易
            self.last_grid_index = grid_index
            return

        # 同一时刻只能有一个线程在执行网格挂单操作以及连续开仓信号的处理
        self.wait_lock_release("grid_orders_lock")
        self.grid_orders_lock = True  # 设置锁，防止多线程冲突

        self.wait_lock_release("continuous_open_signal_lock", "处理连续开仓信号")
        self.continuous_open_signal_lock = True  # 设置锁，防止多线程冲突

        grid_orders_copy = self.grid_orders.copy()
        for grid_index, grid_order in grid_orders_copy.items():
            continuous_open_signal_count = self.continuous_open_signal[grid_index]
            if (
                grid_order["side"] == "sell"
                and grid_order["price"] + 0.00005
                <= sell_price  # 这里的+0.00005调整是因为希望开仓条件苛刻一点，以免频繁的挂单又撤单，下面同理
            ):
                if continuous_open_signal_count < self.continuous_open_signal_min_num:
                    # 如果连续开仓信号小于最小数量，不执行交易
                    self.continuous_open_signal[grid_index] += 1
                    continue
                grid_order["maker_price"] = np.round(
                    bbo_copy[self.future]["bid_price"] + 0.1, 2
                )  # 由于交割合约买卖一档spread很大，可以适当提高买价
                grid_order["maker_price"] = (
                    grid_order["maker_price"]
                    if grid_order["maker_price"] < bbo_copy[self.future]["ask_price"]
                    else bbo_copy[self.future]["bid_price"]
                )
                grid_order["taker_price"] = bbo_copy[self.spot]["bid_price"]
                # 执行卖出操作
                placeSuccess = self._exec_grid_order(grid_order=grid_order)
                if not placeSuccess:
                    continue
                self.trader.log(
                    f"buy_price: {buy_price}, sell_price: {sell_price}\
                        \n执行卖出操作: {json.dumps(grid_order, indent=2)}",
                    level="INFO",
                )
                # 交易执行成功，需要重置连续开仓信号
                self.continuous_open_signal[grid_index] = 0

            elif (
                grid_order["side"] == "buy"
                and grid_order["price"] - 0.00005 >= buy_price
            ):
                if continuous_open_signal_count < self.continuous_open_signal_min_num:
                    # 如果连续开仓信号小于最小数量，不执行交易
                    self.continuous_open_signal[grid_index] += 1
                    continue
                grid_order["maker_price"] = np.round(
                    bbo_copy[self.future]["ask_price"] - 0.1, 2
                )  # 由于交割合约买卖一档spread很大，可以适当降低卖价
                grid_order["maker_price"] = (
                    grid_order["maker_price"]
                    if grid_order["maker_price"] > bbo_copy[self.future]["bid_price"]
                    else bbo_copy[self.future]["ask_price"]
                )
                grid_order["taker_price"] = bbo_copy[self.spot]["ask_price"]
                # 执行买入操作
                placeSuccess = self._exec_grid_order(grid_order=grid_order)
                if not placeSuccess:
                    continue
                self.trader.log(
                    f"buy_price: {buy_price}, sell_price: {sell_price}\
                        \n执行买入操作: {json.dumps(grid_order, indent=2)}",
                    level="INFO",
                )
                # 交易执行成功，需要重置连续开仓信号
                self.continuous_open_signal[grid_index] = 0
            else:
                self.continuous_open_signal[
                    grid_index
                ] -= 5  # 如果不满足开仓条件，减少连续开仓信号计数
                if self.continuous_open_signal[grid_index] < 0:
                    self.continuous_open_signal[grid_index] = 0
                continue

            # 从网格挂单中移除正在执行的订单
            self.grid_orders.pop(grid_index, None)

        self.continuous_open_signal_lock = False  # 释放锁
        self.grid_orders_lock = False  # 释放锁

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
        grid_side = grid_order["side"]
        actual_side = "buy" if grid_side == "sell" else "sell"
        cid = self.trader.create_cid(self.cex_configs[1]["exchange"])
        order = {
            "cid": cid,
            "symbol": self.placeFutureSymbol,  # 使用交割合约符号
            "order_type": "Limit",
            "side": actual_side.capitalize(),
            "amount": grid_order["amount"],  # 使用网格的数量
            "price": grid_order["maker_price"],  # 使用网格的maker价格
            "time_in_force": "PostOnly",  # 持续有效
        }
        # 统计订单延迟
        self.order_delay_stats.add_when_submit(order, "place_order")

        # 统计滑点 - 记录期望价格
        self.slippage_stats.add_when_place(
            order, "grid_order", grid_order["maker_price"]
        )

        # 执行挂单
        place_order_result = self.trader.place_order(1, order)
        if "Err" in place_order_result:
            self.trader.log(
                f"挂单失败: {place_order_result['Err']}",
                level="ERROR",
            )
            return False
        # 记录订单信息
        self.cid_to_grid_pending_order[cid] = grid_order
        self.wait_lock_release("pending_orders_lock", "添加挂单到pending_orders")
        self.pending_orders_lock = True
        self.pending_orders[cid] = order
        self.pending_orders_lock = False  # 释放锁
        return True

    def _market_close_all(self):
        """平掉所有仓位"""
        # 由于有对冲机制，当交割合约成交时永续合约会自动对冲，所以这里只需要平掉现货仓位即可
        symbol = self.spot
        # 平掉所有仓位
        position = self.positions.get(symbol, None)
        if position:
            # 执行平仓操作
            if position["amount"] == 0:
                self.trader.log(
                    f"没有持仓需要平仓: {json.dumps(position, indent=2)}",
                    level="INFO",
                )
                return
            if position["side"].lower() == "long":
                order = {
                    "symbol": symbol,
                    "order_type": "Market",
                    "side": "Sell",
                    "amount": position["amount"],
                    "price": None,  # 市价平仓
                }
                self.trader.place_order(0, order, sync=self.sync)
                self.trader.log(
                    f"市价平仓: {json.dumps(order, indent=2)}",
                    level="INFO",
                )
            elif position["side"].lower() == "short":
                order = {
                    "symbol": symbol,
                    "order_type": "Market",
                    "side": "Buy",
                    "amount": position["amount"],
                    "price": None,  # 市价平仓
                }
                self.trader.place_order(0, order, sync=self.sync)
                self.trader.log(
                    f"市价平仓: {json.dumps(order, indent=2)}",
                    level="INFO",
                )
            # 清除持仓信息
            self.positions[symbol] = None

    def on_order(self, exchange, order):
        """处理订单数据
        exchange: str - 交易所名称
        order: dict - 订单数据
        """
        # 先对symbol进行处理
        order["symbol"] = self.__process_symbol(order["symbol"])

        # 统计延迟
        stats_cid = self.order_delay_stats._create_stats_cid(order)
        if order["status"].lower() == "open":
            if stats_cid in self.order_delay_stats.order_delay_stats["amend_order"]:
                latency = self.order_delay_stats.add_when_recive(order, "amend_order")
                if latency is not None:
                    self.trader.log(
                        f"改单{stats_cid}延迟: {latency} ms",
                        level="INFO",
                    )
            else:
                latency = self.order_delay_stats.add_when_recive(order, "place_order")
                if latency is not None:
                    self.trader.log(
                        f"下单{stats_cid}延迟: {latency} ms",
                        level="INFO",
                    )
        elif order["status"].lower() == "canceled":
            latency = self.order_delay_stats.add_when_recive(order, "cancel_order")
            if latency is not None:
                self.trader.log(
                    f"撤单{stats_cid}延迟: {latency} ms",
                    level="INFO",
                )

        # 统计滑点
        if order["status"].lower() == "filled":
            cid = order["cid"]
            slippage_abs, slippage_bps = None, None
            if cid in self.slippage_stats.order_slippage_stats["grid_order"]:
                slippage_abs, slippage_bps = self.slippage_stats.add_when_filled(
                    order, "grid_order"
                )
            elif cid in self.slippage_stats.order_slippage_stats["hedge_order"]:
                slippage_abs, slippage_bps = self.slippage_stats.add_when_filled(
                    order, "hedge_order"
                )
            if slippage_abs is not None:
                self.trader.log(
                    f"订单{order['cid']}滑点: {slippage_abs:.6f} ({slippage_bps:.2f} bps)",
                    level="INFO",
                )

        # 对冲单成交
        if order["symbol"] == self.spot and order["status"].lower() == "filled":
            # 统计网格成交价
            grid_order_deal_price, grid_order_slippage = (
                self.deal_price_stats.add_deal_hedge_order(hedge_order=order)
            )
            grid_order = self.deal_price_stats.grid_order_stats.get(
                order["cid"], {}
            ).get("grid_order", None)
            self.trader.log(
                f"对冲订单成交: {json.dumps(order, indent=2)}\
                    \n-> 对应网格订单: {json.dumps(grid_order, indent=2)}\
                    \n-> 网格成交价: {grid_order_deal_price}\
                    \n-> 网格滑点: {grid_order_slippage}",
                level="INFO",
            )

        # 交割合约被取消
        if order["symbol"] == self.future and order["status"].lower() == "canceled":
            # 交割合约订单被取消
            self.trader.log(
                f"交割合约订单被取消: {json.dumps(order, indent=2)}",
                level="INFO",
            )
            # 将原网格订单添加到网格挂单列表
            grid_order = self.cid_to_grid_pending_order.get(order["cid"], None)
            if grid_order:
                if "maker_price" in grid_order:
                    del grid_order["maker_price"]
                if "taker_price" in grid_order:
                    del grid_order["taker_price"]
                self.trader.log(
                    f"交割合约订单被取消，重新挂单: {json.dumps(grid_order, indent=2)}",
                    level="INFO",
                )
                self.wait_lock_release("grid_orders_lock")
                self.grid_orders_lock = True  # 设置锁，防止多线程冲突
                self.grid_orders[grid_order["grid_index"]] = grid_order
                self.grid_orders_lock = False  # 释放锁
            # 删除order
            self._remove_pending_order(order["cid"])

        # 一旦交割合约成交，使用永续/现货市价对冲
        if order["symbol"] == self.future and order["status"].lower() == "filled":
            self.trader.log(
                f"交割合约订单成交: {json.dumps(order, indent=2)} \
                    \n-> 对应网格订单: {self.cid_to_grid_pending_order.get(order['cid'], None)}",
                level="INFO",
            )
            side = "Buy" if order["side"] == "Sell" else "Sell"
            amount = order["filled"]
            # 网格订单成交，处理
            grid_order = self.cid_to_grid_pending_order.get(order["cid"], None)
            # 统计成交价格
            hedge_order_cid = self.trader.create_cid(self.cex_configs[0]["exchange"])
            self.deal_price_stats.add_deal_grid_order(
                hedge_order_cid,
                grid_order,
                order["filled_avg_price"],
            )
            # 使用taker价格对冲
            if grid_order is not None and "taker_price" in grid_order:
                self.exec_hedge(
                    hedge_order_cid, self.spot, side, amount, grid_order["taker_price"]
                )
            else:
                self.exec_hedge(hedge_order_cid, self.spot, side, amount)
            if grid_order:
                # 重新挂网格
                new_grid_order = {}
                on_upper = grid_order["side"] == "buy"
                new_grid_order["price"] = (
                    grid_order["price"] + self.grid_interval
                    if on_upper
                    else grid_order["price"] - self.grid_interval
                )
                new_grid_order["amount"] = grid_order["amount"]
                new_grid_order["side"] = "sell" if on_upper else "buy"
                new_grid_order["grid_index"] = (
                    grid_order["grid_index"] + 1
                    if on_upper
                    else grid_order["grid_index"] - 1
                )
                self.trader.log(
                    f"网格订单成交，挂对应的网格单: {json.dumps(new_grid_order, indent=2)}",
                    level="INFO",
                )
                self.wait_lock_release("grid_orders_lock")
                self.grid_orders_lock = True  # 设置锁，防止多线程冲突
                self.grid_orders[new_grid_order["grid_index"]] = new_grid_order
                self.grid_orders_lock = False
            # 删除order
            self._remove_pending_order(order["cid"])

    def exec_hedge(self, cid, symbol, side, amount, price=None):
        """执行对冲操作, 市价对冲
        cid: str - 客户端订单ID
        symbol: str - 交易对
        side: str - 方向，'buy' 或 'sell'
        amount: float - 数量
        price: float - 价格
        """
        if price is None:
            place_price = (
                np.round(
                    (self.bbo[symbol]["bid_price"] * (1 - 0.002)), 2
                )  # 这里使用限价加上0.2%的滑点忍受，2是因为ETH的交割与永续的最小报价单位是0.01
                if side.lower() == "sell"
                else np.round((self.bbo[symbol]["ask_price"] * (1 + 0.002)), 2)
            )
            expected_price = (
                self.bbo[symbol]["bid_price"]
                if side.lower() == "sell"
                else self.bbo[symbol]["ask_price"]
            )
        else:
            place_price = (
                np.round(
                    (price * (1 - 0.002)), 2
                )  # 这里使用限价加上0.2%的滑点忍受，2是因为ETH的交割与永续的最小报价单位是0.01
                if side.lower() == "sell"
                else np.round(price * (1 + 0.002), 2)
            )
            expected_price = price

        # cid = self.trader.create_cid(self.cex_configs[0]["exchange"])
        order = {
            "cid": cid,
            "symbol": symbol,
            "order_type": "Limit",  # 市价对冲使用限价单
            "side": side.capitalize(),
            "amount": amount,
            "price": place_price,
            "time_in_force": "GTC",  # 即时成交剩余撤销
        }
        # 统计订单延迟
        self.order_delay_stats.add_when_submit(order, "place_order")
        # 统计滑点 - 记录期望价格
        self.slippage_stats.add_when_place(order, "hedge_order", expected_price)
        # 执行对冲操作
        self.trader.log(
            f"执行市价对冲操作: {json.dumps(order, indent=2)}",
            level="INFO",
        )
        # 对冲使用同步，如果是异步可能会导致对冲订单未完成就开始下一步操作
        order_result = self.trader.place_order(0, order)
        while "Ok" not in order_result:
            self.trader.log(
                f"对冲订单下单失败: {order_result}, 重试中...",
                level="ERROR",
            )
            time.sleep(0.01)  # 等待0.01秒后重试
            order_result = self.trader.place_order(0, order)

    def on_position(self, exchange, position):
        """处理持仓数据
        exchange: str - 交易所名称
        position: dict - 持仓数据
        """
        if isinstance(position, list):
            # 如果是列表，说明是多个持仓数据
            for pos in position:
                self.on_position(exchange, pos)
            return
        # 先对symbol进行处理
        position["symbol"] = self.__process_symbol(position["symbol"])

        self.trader.log(
            f"接收到持仓数据: {json.dumps(position, indent=2)}",
            level="INFO",
        )

        # 更新持仓信息
        self.positions[position["symbol"]] = position
