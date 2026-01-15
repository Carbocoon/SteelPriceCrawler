import streamlit as st
import pandas as pd
import os
import time
import logging
import io
from datetime import datetime

# 设置页面配置
st.set_page_config(
    page_title="钢材数据采集助手",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 确保当前目录在 sys.path 中 (解决打包后无法导入的问题)
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# 导入爬虫类
try:
    from crawler_haoganghui import HaoganghuiSpider
    from crawler_xinggang91 import XinggangSeleniumSpider
except ImportError as e:
    st.error(f"无法导入爬虫脚本，请确保 crawler_haoganghui.py 和 crawler_xinggang91.py 在同一目录下。\n详细错误: {e}")
except Exception as e:
    st.error(f"导入时发生意外错误: {e}")

# 初始化 Session State
if 'spider' not in st.session_state:
    st.session_state.spider = None
if 'spider_type' not in st.session_state:
    st.session_state.spider_type = None
if 'crawled_data' not in st.session_state:
    st.session_state.crawled_data = None

# 自定义 CSS 美化
st.markdown("""
<style>
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    /* 按钮样式优化 */
    .stButton button {
        font-weight: 600;
        border-radius: 8px;
        height: 3rem;
    }
    /* 标题样式 */
    h1 {
        color: #1E88E5;
        font-size: 2.5rem !important;
    }
    /* 卡片样式 */
    div.stMetric {
        border: 1px solid rgba(128, 128, 128, 0.2);
        padding: 15px;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

# 自定义日志处理器
class StreamlitLogger(logging.Handler):
    def __init__(self, container):
        super().__init__()
        self.container = container
        self.logs = []

    def emit(self, record):
        msg = self.format(record)
        self.logs.append(msg)
        # 保持显示最新的 15 条日志
        self.container.code("\n".join(self.logs[-15:]), language="text")

def main():
    # 顶部标题区域
    col_header, col_logo = st.columns([5, 1])
    with col_header:
        st.title("🏗️ 钢材数据采集助手")
        st.markdown("#### 自动化采集 **好钢汇** 与 **91型钢** 市场实时数据")
    
    # 侧边栏配置
    with st.sidebar:
        st.header("⚙️ 采集配置")
        
        st.subheader("1. 选择目标平台")
        # 如果爬虫已启动，禁用选择
        disabled = st.session_state.spider is not None
        spider_type_selection = st.radio(
            "目标网站",
            ["好钢汇 (Haoganghui)", "91型钢 (Xinggang91)"],
            captions=["haoganghui.cn", "91xinggang.com"],
            index=0,
            disabled=disabled
        )
        
        st.subheader("2. 运行模式")
        # 检测是否在 Linux (Streamlit Cloud) 环境
        is_linux_server = sys.platform.startswith('linux')
        
        headless_default = True if is_linux_server else False
        headless_help = "开启后浏览器将隐藏在后台运行。"
        if is_linux_server:
            headless_help += " (检测到云服务器环境，强制开启无头模式)"

        headless = st.toggle(
            "无头模式 (后台运行)", 
            value=headless_default,
            help=headless_help,
            disabled=disabled or is_linux_server
        )
        
        st.divider()
        
        with st.expander("💡 使用指南", expanded=True):
            st.markdown("""
            **操作流程：**
            1. **启动浏览器**：点击"启动浏览器"按钮。
            2. **登录/查页数**：在弹出的浏览器中登录，并确认总页数。
            3. **输入页数**：在下方输入框填写总页数。
            4. **开始采集**：点击"开始采集"。
            """)
            
        st.caption(f"当前日期: {datetime.now().strftime('%Y-%m-%d')}")

    # 主操作区域
    st.markdown("---")

    # 状态容器
    status_container = st.container()
    
    # 日志区域 (始终显示)
    with status_container:
        log_expander = st.expander("🖥️ 实时运行日志", expanded=True)
        with log_expander:6
        log_placeholder = st.empty()
        
        # 配置日志系统
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        # 清理旧处理器
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # 添加新的处理器
        st_handler = StreamlitLogger(log_placeholder)
        formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s', datefmt='%H:%M:%S')
        st_handler.setFormatter(formatter)
        logger.addHandler(st_handler)
        
        # 同时输出到控制台
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # 逻辑分流
    if st.session_state.crawled_data is not None:
        # === 阶段 3: 结果展示 ===
        st.balloons()
        st.success("✅ 采集任务完成！")
        
        data = st.session_state.crawled_data
        
        # 结果统计
        st.markdown("### 📊 结果统计")
        m1, m2 = st.columns(2)
        m1.metric("获取数据条数", f"{len(data)} 条")
        m2.metric("状态", "已完成")
        
        # 数据处理
        df = pd.DataFrame(data)
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        site_code = "haoganghui" if "好钢汇" in st.session_state.spider_type else "xinggang91"
        filename = f"钢材数据_{site_code}_{timestamp}.csv"
        
        # 选项卡显示数据和下载
        tab_preview, tab_download = st.tabs(["👀 数据预览", "💾 下载数据"])
        
        with tab_preview:
            st.dataframe(df, use_container_width=True)
        
        with tab_download:
            col_csv, col_xlsx = st.columns(2)
            
            with col_csv:
                csv = df.to_csv(index=False, encoding='utf-8-sig')
                st.download_button(
                    label="📥 下载 CSV 格式",
                    data=csv,
                    file_name=filename,
                    mime="text/csv",
                    use_container_width=True
                )
            
            with col_xlsx:
                # Excel download
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Sheet1')
                excel_data = output.getvalue()
                
                st.download_button(
                    label="📥 下载 Excel 格式",
                    data=excel_data,
                    file_name=filename.replace('.csv', '.xlsx'),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
        
        st.markdown("---")
        # 添加显眼的开始新任务按钮
        if st.button("🔄 开始新任务 (返回首页)", type="primary", use_container_width=True):
            # 清除所有状态以完全重置
            st.session_state.clear()
            st.rerun()

    elif st.session_state.spider is None:
        # === 阶段 1: 启动浏览器 ===
        st.info("👋 欢迎使用！请先启动浏览器进行登录操作。")
        
        col_launch, col_space = st.columns([1, 3])
        with col_launch:
            if st.button("🚀 第1步：启动浏览器", type="primary", use_container_width=True):
                try:
                    with st.spinner('正在启动浏览器...'):
                        if "好钢汇" in spider_type_selection:
                            spider = HaoganghuiSpider(headless=headless, interactive=False)
                        else:
                            spider = XinggangSeleniumSpider(headless=headless, interactive=False)
                        
                        # 立即打开网页
                        spider.driver.get(spider.url)
                        
                        # 保存到 Session State
                        st.session_state.spider = spider
                        st.session_state.spider_type = spider_type_selection
                        st.rerun()
                        
                except Exception as e:
                    st.error(f"启动失败: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())

    else:
        # === 阶段 2: 输入页数并采集 ===
        st.success(f"✅ 浏览器已启动 ({st.session_state.spider_type})！请在浏览器中完成登录，并查看总页数。")
        
        col_input, col_actions = st.columns([1, 2])
        
        with col_input:
            max_pages = st.number_input(
                "请输入要采集的总页数", 
                min_value=1, 
                value=3, 
                step=1,
                help="请根据网页显示的实际页数填写"
            )
        
        with col_actions:
            st.write("") # Spacer
            st.write("") # Spacer
            c1, c2 = st.columns(2)
            with c1:
                start_crawl = st.button("🏃‍♂️ 第2步：开始采集", type="primary", use_container_width=True)
            with c2:
                cancel = st.button("❌ 取消/关闭", type="secondary", use_container_width=True)
        
        if cancel:
            try:
                st.session_state.spider.driver.quit()
            except:
                pass
            st.session_state.spider = None
            st.rerun()
            
        if start_crawl:
            spider = st.session_state.spider
            should_rerun = False
            
            try:
                st.info("正在开始采集，请勿关闭浏览器...")
                
                # 执行爬取
                # skip_init=True: 跳过初始化访问和登录检查，因为用户已经在浏览器中操作过了
                # close_on_finish=False: 爬取完成后不关闭浏览器，由 Streamlit 控制
                if "好钢汇" in st.session_state.spider_type:
                    data = spider.crawl(max_pages=max_pages, skip_init=True)
                else:
                    data = spider.crawl(max_pages=max_pages, skip_init=True, close_on_finish=False)
                
                if data:
                    # 保存数据到 session state
                    st.session_state.crawled_data = data
                    
                    # 不再自动保存到本地，由用户点击下载按钮保存
                    # try:
                    #     spider.save_data()
                    # except:
                    #     pass
                    
                    # 清理 spider 对象 (driver 已经在 crawl 内部关闭了)
                    st.session_state.spider = None
                    should_rerun = True
                else:
                    st.error("❌ 未能获取到数据。请检查日志。")
            
            except Exception as e:
                st.error(f"❌ 发生错误: {str(e)}")
                import traceback
                st.code(traceback.format_exc())
            
            except BaseException as e:
                # 处理中断 (如用户点击停止按钮)
                st.warning("⚠️ 任务被中断。正在尝试保存已获取的数据...")
                if spider and spider.data:
                    try:
                        saved_file = spider.save_data()
                        st.success(f"✅ 已紧急保存 {len(spider.data)} 条数据到: {saved_file}")
                        
                        # 即使中断，也显示已获取的数据
                        st.session_state.crawled_data = spider.data
                        st.session_state.spider = None
                        should_rerun = True
                        
                    except Exception as save_err:
                        st.error(f"保存失败: {save_err}")
            
            finally:
                # 如果 driver 还没关（例如被中断），尝试关闭
                if spider and hasattr(spider, 'driver'):
                    try:
                        spider.driver.quit()
                    except:
                        pass
            
            if should_rerun:
                st.rerun()

if __name__ == "__main__":
    main()
