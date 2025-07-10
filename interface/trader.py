from abc import ABC, abstractmethod


class Trader(ABC):
    @abstractmethod
    def publish(self, cmd):
        """发布交易指令"""
        pass

    @abstractmethod
    def batch_publish(self, cmds):
        """批量发布交易指令"""
        pass

    @abstractmethod
    def create_cid(self, exchange):
        """创建唯一的客户端标识符"""
        pass

    @abstractmethod
    def graceful_shutdown(self):
        """优雅退出交易进程"""
        pass

    # 日志管理
    @abstractmethod
    def log(self, msg, level=None, color=None, web=True):
        """记录日志到控制台和Web平台"""
        pass

    @abstractmethod
    def tlog(self, tag, msg, color=None, interval=0, level=None, query=False):
        """限频日志记录"""
        pass

    @abstractmethod
    def logt(self, message, time, color=None, level=None):
        """使用指定时间戳记录日志"""
        pass

    # 缓存管理
    @abstractmethod
    def cache_save(self, data):
        """保存数据到缓存系统"""
        pass

    @abstractmethod
    def cache_load(self):
        """从缓存系统加载数据"""
        pass

    # 外部通信
    @abstractmethod
    def http_request(self, url, method, body, headers=None):
        """发送HTTP请求获取外部数据"""
        pass

    # NB8 Web平台集成
    @abstractmethod
    def init_web_client(self, config):
        """创建并初始化WebClient"""
        pass

    @abstractmethod
    def start_web_client(self, upload_interval=None):
        """启动WebClient"""
        pass

    @abstractmethod
    def stop_web_client(self):
        """停止WebClient"""
        pass

    @abstractmethod
    def is_web_soft_stopped(self):
        """检查平台是否下发了缓停指令"""
        pass

    @abstractmethod
    def is_web_opening_stopped(self):
        """检查平台是否下发了停止开仓指令"""
        pass

    @abstractmethod
    def is_web_force_closing(self):
        """检查平台是否下发了强平指令"""
        pass

    @abstractmethod
    def update_total_balance(
        self,
        primary_balance,
        secondary_balance=None,
        available_primary=None,
        available_secondary=None,
    ):
        """更新账户余额信息到Web平台"""
        pass

    @abstractmethod
    def add_funding_fee(self, primary_fee=None, secondary_fee=None):
        """添加已结算的资金费用记录到Web平台"""
        pass

    @abstractmethod
    def update_pred_funding(self, primary_fee=None, secondary_fee=None):
        """更新未结算的预测资金费用记录到Web平台"""
        pass

    @abstractmethod
    def update_total_position_value(
        self, total_value, long_position_value, short_position_value
    ):
        """更新所有节点持仓价值信息到Web平台"""
        pass

    @abstractmethod
    def update_current_position_value(
        self, total_value, long_position_value, short_position_value
    ):
        """更新当前节点持仓价值信息到Web平台"""
        pass

    @abstractmethod
    def update_floating_profit(self, floating_profit):
        """更新浮动盈亏信息到Web平台"""
        pass

    @abstractmethod
    def log_profit(self, profit):
        """上传利润，前端实盘页用来展示利润曲线"""
        pass

    @abstractmethod
    def update_trade_stats(
        self, maker_volume, taker_volume, profit, is_single_close=False
    ):
        """更新交易统计数据到Web平台"""
        pass

    @abstractmethod
    def get_stats(self):
        """获取当前完整的统计数据"""
        pass

    @abstractmethod
    def upload_tables(self, tables):
        """上传多个表格数据到Web平台显示"""
        pass

    @abstractmethod
    def set_force_stop(self, force_stop):
        """直接设置实盘强停状态"""
        pass

    # 交易所API直接访问 - 订单管理
    @abstractmethod
    def get_orders(self, account_id, symbol, start, end, extra=None, generate=False):
        """获取指定时间范围内的订单列表"""
        pass

    @abstractmethod
    def get_open_orders(self, account_id, symbol, extra=None, generate=False):
        """获取指定交易对的未成交订单列表"""
        pass

    @abstractmethod
    def get_all_open_orders(self, account_id, extra=None, generate=False):
        """获取账户下所有交易对的未成交订单"""
        pass

    @abstractmethod
    def get_order_by_id(
        self, account_id, symbol, order_id=None, cid=None, extra=None, generate=False
    ):
        """通过订单ID或客户端订单ID查询单个订单详情"""
        pass

    @abstractmethod
    def place_order(
        self, account_id, order, params=None, extra=None, sync=True, generate=False
    ):
        """下单"""
        pass

    @abstractmethod
    def batch_place_order(
        self, account_id, orders, params=None, extra=None, sync=True, generate=False
    ):
        """批量下单"""
        pass

    @abstractmethod
    def amend_order(self, account_id, order, extra=None, sync=True, generate=False):
        """修改订单"""
        pass

    @abstractmethod
    def cancel_order(
        self,
        account_id,
        symbol,
        order_id=None,
        cid=None,
        extra=None,
        sync=True,
        generate=False,
    ):
        """取消订单"""
        pass

    @abstractmethod
    def batch_cancel_order(
        self, account_id, symbol, extra=None, sync=True, generate=False
    ):
        """批量取消指定交易对的所有未成交订单"""
        pass

    @abstractmethod
    def batch_cancel_order_by_id(
        self,
        account_id,
        symbol=None,
        order_ids=None,
        client_order_ids=None,
        extra=None,
        sync=True,
        generate=False,
    ):
        """批量取消指定ID的订单"""
        pass

    # 基础请求
    @abstractmethod
    def request(
        self,
        account_id,
        method,
        path,
        auth,
        query=None,
        body=None,
        url=None,
        headers=None,
        generate=False,
    ):
        """向交易所发送原始API请求"""
        pass

    # 持仓与账户
    @abstractmethod
    def get_position(self, account_id, symbol, extra=None, generate=False):
        """获取指定交易对的持仓信息"""
        pass

    @abstractmethod
    def get_positions(self, account_id, extra=None, generate=False):
        """获取账户下所有持仓信息"""
        pass

    @abstractmethod
    def get_max_position(
        self, account_id, symbol, level=None, extra=None, generate=False
    ):
        """获取交易对的最大可开仓数量"""
        pass

    @abstractmethod
    def get_usdt_balance(self, account_id, extra=None, generate=False):
        """获取账户USDT余额"""
        pass

    @abstractmethod
    def get_balances(self, account_id, extra=None, generate=False):
        """获取账户所有币种余额"""
        pass

    @abstractmethod
    def get_balance_by_coin(self, account_id, asset, extra=None, generate=False):
        """获取指定币种的余额"""
        pass

    @abstractmethod
    def get_fee_rate(self, account_id, symbol, extra=None, generate=False):
        """获取交易对的手续费率"""
        pass

    @abstractmethod
    def get_fee_discount_info(self, account_id, extra=None, generate=False):
        """获取费用折扣信息"""
        pass

    @abstractmethod
    def is_fee_discount_enabled(self, account_id, extra=None, generate=False):
        """检查费用折扣是否已启用"""
        pass

    @abstractmethod
    def set_fee_discount_enabled(self, account_id, enabled, extra=None, generate=False):
        """设置费用折扣启用状态"""
        pass

    # 市场数据
    @abstractmethod
    def get_ticker(self, account_id, symbol, extra=None, generate=False):
        """获取指定交易对的行情数据"""
        pass

    @abstractmethod
    def get_tickers(self, account_id, extra=None, generate=False):
        """获取所有交易对的行情数据"""
        pass

    @abstractmethod
    def get_bbo(self, account_id, symbol, extra=None, generate=False):
        """获取交易对的最优买卖报价"""
        pass

    @abstractmethod
    def get_bbo_tickers(self, account_id, extra=None, generate=False):
        """获取所有交易对的最优买卖报价"""
        pass

    @abstractmethod
    def get_depth(self, account_id, symbol, limit=None, extra=None, generate=False):
        """获取交易对的深度数据"""
        pass

    @abstractmethod
    def get_instrument(self, account_id, symbol, extra=None, generate=False):
        """获取交易对的详细信息"""
        pass

    @abstractmethod
    def get_instruments(self, account_id, extra=None, generate=False):
        """获取所有可交易的交易对信息"""
        pass

    @abstractmethod
    def get_mark_price(self, account_id, symbol=None, extra=None, generate=False):
        """获取标记价格"""
        pass

    @abstractmethod
    def get_funding_rates(self, account_id, extra=None, generate=False):
        """获取所有交易对的资金费率"""
        pass

    @abstractmethod
    def get_funding_rate_by_symbol(
        self, account_id, symbol, extra=None, generate=False
    ):
        """获取指定交易对的资金费率"""
        pass

    @abstractmethod
    def get_funding_rate_history(
        self,
        account_id,
        symbol=None,
        since_secs=None,
        limit=100,
        extra=None,
        generate=False,
    ):
        """获取资金费率历史记录"""
        pass

    @abstractmethod
    def get_funding_fee(
        self,
        account_id,
        symbol,
        start_time=None,
        end_time=None,
        extra=None,
        generate=False,
    ):
        """查询指定交易对的历史资金费用记录"""
        pass

    @abstractmethod
    def get_kline(
        self,
        account_id,
        symbol,
        interval,
        start_time=None,
        end_time=None,
        limit=None,
        extra=None,
        generate=False,
    ):
        """获取指定交易对的K线数据"""
        pass

    # 账户设置与杠杆管理
    @abstractmethod
    def get_max_leverage(self, account_id, symbol, extra=None, generate=False):
        """获取交易对的最大可用杠杆倍数"""
        pass

    @abstractmethod
    def set_leverage(self, account_id, symbol, leverage, extra=None, generate=False):
        """设置交易对的杠杆倍数"""
        pass

    @abstractmethod
    def get_margin_mode(
        self, account_id, symbol, margin_coin, extra=None, generate=False
    ):
        """获取交易对的保证金模式"""
        pass

    @abstractmethod
    def set_margin_mode(
        self, account_id, symbol, margin_coin, margin_mode, extra=None, generate=False
    ):
        """设置交易对的保证金模式"""
        pass

    @abstractmethod
    def is_dual_side(self, account_id, extra=None, generate=False):
        """查询账户是否使用双向持仓模式"""
        pass

    @abstractmethod
    def set_dual_side(self, account_id, dual_side, extra=None, generate=False):
        """设置账户的持仓模式"""
        pass

    # 资金划转与借贷
    @abstractmethod
    def transfer(self, account_id, transfer, extra=None, generate=False):
        """在账户内部或不同账户之间划转资金"""
        pass

    @abstractmethod
    def sub_transfer(self, account_id, sub_transfer, extra=None, generate=False):
        """主账户和子账户之间划转资金"""
        pass

    @abstractmethod
    def get_deposit_address(
        self, account_id, ccy, chain=None, amount=None, extra=None, generate=False
    ):
        """获取指定币种的充值地址"""
        pass

    @abstractmethod
    def withdrawal(self, account_id, withdrawal, extra=None, generate=False):
        """提币到外部地址或内部转账"""
        pass

    @abstractmethod
    def borrow(self, account_id, coin, amount, extra=None, generate=False):
        """借入资金"""
        pass

    @abstractmethod
    def repay(self, account_id, coin, amount, extra=None, generate=False):
        """偿还借入的资金"""
        pass

    @abstractmethod
    def get_borrowed(self, account_id, coin=None, extra=None, generate=False):
        """查询已借入的资金"""
        pass

    @abstractmethod
    def get_borrow_rate(self, account_id, coin=None, extra=None, generate=False):
        """查询借贷利率"""
        pass

    @abstractmethod
    def get_borrow_limit(
        self, account_id, coin, is_vip=None, extra=None, generate=False
    ):
        """查询借贷限额"""
        pass

    # 账户信息
    @abstractmethod
    def get_account_info(self, account_id, extra=None, generate=False):
        """获取账户详细信息"""
        pass

    @abstractmethod
    def get_account_mode(self, account_id, extra=None, generate=False):
        """获取账户模式"""
        pass

    @abstractmethod
    def set_account_mode(self, account_id, account_mode, extra=None, generate=False):
        """设置账户模式"""
        pass

    @abstractmethod
    def get_user_id(self, account_id, extra=None, generate=False):
        """获取用户ID"""
        pass
