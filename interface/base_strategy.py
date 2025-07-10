"""
strategy.py

这个文件定义了 BaseStrategy 基类, 实现了相关的事件处理和策略逻辑。便于用户继承并实现自己的策略。
"""


class BaseStrategy:

    def name(self):
        """
        返回策略的名称。

        Returns:
            str: 策略名称。
        """
        return "Base Strategy"

    def start(self):
        """
        启动策略执行。

        在这里执行策略初始化的操作,比如查询交易币种信息, 设置杠杆等
        """
        print("Starting Base Strategy")

    def subscribes(self):
        """
        返回策略订阅的事件列表。

        订阅分为两种类型:
            SubscribeWs: 订阅交易所相关 websocket 频道, 接收到消息会推到策略回调。
                支持的订阅频道：
                    - MarkPrice: 标记价格
                    - Bbo: 最佳买卖价
                    - Depth: 市场深度
                    - Kline: K线数据
                    - Funding: 资金费率
                    - Trade: 成交
                    - Order: 订单
                    - Position: 仓位
                    - Balance: 余额
                    - FundingFee: 结算资金费
                    - OrderAndFill: 订单和用户私有成交

            SubscribeRest: 会起异步任务使用 HTTP 定期轮询某些接口并推送到策略回调。
                支持轮询的接口：
                    - Funding: 资金费率
                    - Balance: 余额
                    - Position: 仓位
                    - Instrument: 合约信息

            SubscribeTimer: 会起异步任务定时执行on_timer_subscribe回调。

        Returns:
            list: 订阅的事件列表。
        """
        return []

    def on_ws_connected(self, exchange, account_id):
        """
        WebSocket 连接建立时触发的方法。

        Args:
            exchange (str): 交易所名称。
            account_id (str): 账户 ID。
        """
        pass

    def on_ws_disconnected(self, exchange, account_id):
        """
        WebSocket 连接断开时触发的方法。

        Args:
            exchange (str): 交易所名称。
            account_id (str): 账户 ID。
        """
        pass

    def on_latency(self, latency, account_id):
        """
        延迟统计时触发的方法。

        Args:
            latency (dict): 延迟信息。
            account_id (str): 账户 ID。
        """
        pass

    def on_cmd(self, cmd):
        """
        命令执行时触发的方法。

        Args:
            cmd (dict): 命令信息。
        """
        pass

    def on_timer_subscribe(self, timer_name):
        """
        定时器触发时触发的方法。

        Args:
            timer_name (str): 定时器名称。
        """
        pass

    def on_order_submitted(self, account_id, order_id_result, order):
        """
        订单提交成功时触发的方法。

        Args:
            account_id (str): 账户 ID。

            order_result (str): 包含订单 ID 的 Result 可能为 Err。
            order (dict): 订单信息。
        """
        pass

    def on_batch_order_submitted(self, account_id, order_ids_result):
        """
        批量订单提交成功时触发的方法。

        Args:
            account_id (str): 账户 ID。

            order_ids (list): 订单 ID 列表。
        """
        pass

    def on_order_canceled(self, account_id, result, id, symbol):
        """
        订单取消成功时触发的方法。

        Args:
            account_id (str): 账户 ID。
            order_id (str): 订单 ID。
            id (str): 撤单时传入的订单id/订单cid。
            symbol(str): 撤单时传入的symbol。
        """
        pass

    def on_batch_order_canceled(self, account_id, order_ids_result):
        """
        批量订单取消成功时触发的方法。

        Args:
            account_id (str): 账户 ID。
            order_ids (list): 订单 ID 列表。
        """
        pass

    def on_batch_order_canceled_by_ids(self, account_id, order_ids_result):
        """
        批量订单取消成功时触发的方法。

        Args:
            account_id (str): 账户 ID。
            order_ids (list): 订单 ID 列表。
        """
        pass

    def on_order_amended(self, account_id, result, order):
        """
        订单修改成功时触发的方法。

        Args:
            account_id (str): 账户 ID。
            order_id (str): 订单 ID。
            order(dict): 修改订单时传入的订单信息
        """
        pass

    def on_order(self, account_id, order):
        """
        订单状态更新时触发的方法。

        Args:
            account_id (str): 账户 ID。
            order: 订单对象。
        """
        pass

    def on_order_and_fill(self, account_id, order):
        """
        订单/用户私有成交更新时触发的方法, 订单频道和用户成交频道哪个快推哪个。

        Args:
            account_id (str): 账户 ID。
            order: 订单对象。
        """
        pass

    def on_funding_fee(self, account_id, funding_fee):
        """
        资金费结算时触发的方法。

        Args:
            account_id (str): 账户 ID。
            funding_fee: 资金费对象。
        """
        pass

    def on_position(self, account_id, positions):
        """
        持仓更新时触发的方法。

        Args:
            account_id (str): 账户 ID。
            positions: 持仓对象列表。
        """
        pass

    def on_balance(self, account_id, balances):
        """
        账户余额更新时触发的方法。

        Args:
            account_id (str): 账户 ID。
            balance: 余额对象。
        """
        pass

    def on_bbo(self, exchange, bbo):
        """
        最佳买卖价变动时触发的方法。

        Args:
            exchange (str): 交易所名称。
            bbo: 最佳买一卖一。
        """
        pass

    def on_depth(self, exchange, depth):
        """
        市场深度更新时触发的方法。

        Args:
            exchange (str): 交易所名称。
            depth: 市场深度对象。
        """
        pass

    def on_ticker(self, exchange, ticker):
        """
        最新成交价更新时触发的方法。

        Args:
            exchange (str): 交易所名称。
            ticker: 行情数据对象。
        """
        pass

    def on_trade(self, exchange, trade):
        """
        成交更新时触发的方法。

        Args:
            exchange (str): 交易所名称。
            trade: 成交对象。
        """
        pass

    def on_funding(self, exchange, fundings):
        """
        资金费率更新时触发的方法。

        Args:
            exchange (str): 交易所名称。
            fundings: 资金费率对象列表。
        """
        pass

    def on_mark_price(self, exchange, mark_price):
        """
        标记价格更新时触发的方法。

        Args:
            exchange (str): 交易所名称。
            mark_price: 标记价格。
        """
        pass

    def on_kline(self, exchange, kline):
        """
        行情K线更新时触发的方法。

        Args:
            exchange (str): 交易所名称。
            kline: 行情K线对象。
        """
        pass

    def on_instrument(self, exchange, instruments):
        """
        交易对信息更新时触发的方法。

        Args:
            exchange (str): 交易所名称。
            instruments: 合约信息对象列表。
        """
        pass

    def on_instrument_added(self, exchange, instruments):
        """
        交易对信息新增时触发的方法。
        """
        pass

    def on_instrument_updated(self, exchange, instruments):
        """
        交易对信息更新时触发的方法。
        """
        pass

    def on_instrument_removed(self, exchange, instruments):
        """
        交易对信息删除时触发的方法。
        """
        pass

    def on_dex_data(self, account_id, data):
        """
        DEX 数据更新时触发的方法。

        Args:
            account_id (str): 账户 ID。
            data: 数据对象。
        """
        pass

    def on_stop(self):
        """
        停止策略时触发的方法。
        """
        pass

    def on_config_update(self, config):
        """
        热更新策略配置时触发的方法。

        Args:
            config: 配置。
        """
        pass
