import time
import pandas as pd
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import undetected_chromedriver as uc
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s: %(message)s')

class XinggangSeleniumSpider:
    def __init__(self, headless=False, interactive=True):
        self.url = "https://www.91xinggang.com/#/matchMarket"
        self.interactive = interactive
        self.data = []
        self.setup_driver(headless)
        
    def setup_driver(self, headless=False):
        """设置Chrome驱动"""
        # 优先使用普通selenium驱动，因为undetected_chromedriver在某些环境可能不稳定
        # 如果需要使用undetected_chromedriver，请取消注释以下代码并注释掉 self.setup_regular_driver(headless)
        self.setup_regular_driver(headless)
        return

        # logging.info("正在初始化浏览器驱动...")
        # 
        # try:
        #     options = uc.ChromeOptions()
        #     
        #     if headless:
        #         options.add_argument('--headless')
        #     
        #     # 添加常用参数
        #     options.add_argument('--no-sandbox')
        #     options.add_argument('--disable-dev-shm-usage')
        #     options.add_argument('--disable-gpu')
        #     options.add_argument('--window-size=1920,1080')
        #     options.add_argument('--disable-blink-features=AutomationControlled')
        #     
        #     # 添加user-agent
        #     options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36')
        #     
        #     # 禁用自动化控制标志
        #     options.add_experimental_option("excludeSwitches", ["enable-automation"])
        #     options.add_experimental_option('useAutomationExtension', False)
        #     
        #     # 创建驱动
        #     self.driver = uc.Chrome(options=options)
        #     
        #     # 执行JavaScript隐藏自动化特征
        #     self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        #     
        #     logging.info("浏览器驱动初始化完成")
        #     
        # except Exception as e:
        #     logging.error(f"驱动初始化失败: {e}")
        #     # 尝试使用普通selenium
        #     self.setup_regular_driver(headless)
    
    def setup_regular_driver(self, headless=False):
        """使用普通selenium驱动"""
        try:
            chrome_options = Options()
            if headless:
                chrome_options.add_argument('--headless')
            
            # 关键参数：解决容器环境/Server Crash 问题
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')

            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36')
            
            # 添加stealth.js避免被检测
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            self.driver = webdriver.Chrome(options=chrome_options)
            logging.info("普通Chrome驱动初始化完成")
            
        except Exception as e:
            logging.error(f"普通驱动也失败: {e}")
            raise
    
    def wait_for_page_load(self, timeout=30):
        """等待页面加载"""
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            logging.info("页面加载完成")
        except Exception as e:
            logging.warning(f"等待页面加载超时: {e}")
    
    def login_if_needed(self):
        """如果需要登录，先登录"""
        try:
            logging.info("准备进行登录检查...")
            
            # 强制提示用户手动登录，因为价格数据通常需要登录权限
            print("\n" + "="*50)
            print("【重要提示】")
            print("该网站的价格数据通常需要登录才能查看。")
            print("请在弹出的浏览器窗口中：")
            print("1. 点击页面上的'登录'按钮")
            print("2. 完成登录操作（扫码或账号密码）")
            print("3. 确认页面上能看到具体价格（而不是'登录后查看'）")
            print("="*50)
            
            # 等待用户确认
            if self.interactive:
                user_input = input("\n登录完成后，请按回车键继续 (输入 's' 跳过登录): ")
                
                if user_input.lower() == 's':
                    logging.info("用户选择跳过登录，继续爬取...")
                else:
                    logging.info("用户确认已登录，继续爬取...")
                    time.sleep(2)
            else:
                logging.info("非交互模式：等待45秒供用户手动登录...")
                time.sleep(45)
                
        except Exception as e:
            logging.error(f"登录过程出错: {e}")

    
    def extract_table_data(self):
        """提取表格数据"""
        try:
            logging.info("正在定位表格数据...")
            
            # 等待表格加载
            time.sleep(5)
            
            # 尝试多种方式定位表格
            table_selectors = [
                "div.el-table",
                "div.table-container",
                "table",
                ".ant-table",
                "[class*='table']"
            ]
            
            table = None
            for selector in table_selectors:
                try:
                    table = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if table and table.is_displayed():
                        logging.info(f"使用选择器找到表格: {selector}")
                        break
                except:
                    continue
            
            if not table:
                logging.warning("未找到表格元素，尝试截图查看页面结构")
                self.driver.save_screenshot("page_screenshot.png")
                
                # 尝试获取页面HTML进行分析
                page_source = self.driver.page_source
                with open("page_source.html", "w", encoding="utf-8") as f:
                    f.write(page_source)
                logging.info("已保存页面HTML到page_source.html")
                return []
            
            # 获取表格行
            rows = table.find_elements(By.CSS_SELECTOR, "tr, .el-table__row, .ant-table-row")
            
            if not rows:
                # 尝试另一种方式
                rows = self.driver.find_elements(By.CSS_SELECTOR, "[class*='row'], [class*='tr']")
            
            logging.info(f"找到 {len(rows)} 行数据")
            
            extracted_data = []
            
            for i, row in enumerate(rows[:50]):  # 限制处理前50行
                try:
                    # 获取行文本
                    row_text = row.text.strip()
                    
                    if row_text and len(row_text.split()) > 2:
                        # 解析行数据
                        # 仅查找直接的单元格元素，避免获取到嵌套的span/div文本导致重复
                        cells = row.find_elements(By.CSS_SELECTOR, "td, .el-table__cell, .ant-table-cell")
                        
                        cell_texts = []
                        for cell in cells:
                            # 获取直接文本，或者如果单元格内有特定结构，获取其主要文本
                            text = cell.text.strip()
                            # 过滤掉空文本，但保留占位符以保持索引对齐
                            # if text: 
                            cell_texts.append(text)
                        
                        # 如果没有找到标准的td/cell，尝试更宽泛的搜索但限制层级
                        if not cell_texts:
                             cells = row.find_elements(By.XPATH, "./div | ./span")
                             cell_texts = [c.text.strip() for c in cells]

                        if cell_texts:
                            # 根据实际格式解析数据
                            item = self.parse_row_data(cell_texts, row_text)
                            if item:
                                extracted_data.append(item)
                        
                        logging.debug(f"第{i+1}行: {row_text}")
                        
                except Exception as e:
                    logging.debug(f"处理第{i+1}行时出错: {e}")
                    continue
            
            return extracted_data
            
        except Exception as e:
            logging.error(f"提取表格数据失败: {e}")
            return []
    
    def parse_row_data(self, cells, row_text):
        """解析行数据"""
        try:
            # 创建数据项
            item = {
                # '原始数据': row_text,
                '品名': '',
                '材质': '',
                '规格': '',
                '负差': '',
                '支/件': '',
                '支重(吨)': '',
                '可售量': '',
                '价格(元/吨)': '',
                '品牌': '',
                # '解析时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # 优先使用cells列表进行位置映射
            # 假设列顺序: 品名(0), 材质(1), 规格(2), 负差(3), 支/件(4), 支重(5), 可售量(6), 价格(7), 仓库/产地(8)
            if len(cells) >= 8:
                item['品名'] = cells[0]
                item['材质'] = cells[1]
                item['规格'] = cells[2]
                item['负差'] = cells[3].replace('-', '~')
                item['支/件'] = cells[4]
                item['支重(吨)'] = cells[5]
                item['可售量'] = cells[6]
                
                # 价格处理: 提取数字
                price_raw = cells[7]
                import re
                price_match = re.search(r'(\d{1,3}(,\d{3})*(\.\d+)?)', price_raw)
                if price_match:
                    item['价格(元/吨)'] = price_match.group(1).replace(',', '')
                else:
                    item['价格(元/吨)'] = price_raw
                
                # 处理品牌 (从仓库/产地中提取产地)
                if len(cells) >= 9:
                    warehouse_origin = cells[8].strip()
                    item['品牌'] = warehouse_origin # 默认使用全部内容
                    
                    # 优先处理换行符 (用户提到的情况: 晋南厂库 \n 晋南)
                    if '\n' in warehouse_origin:
                        parts = warehouse_origin.split('\n')
                        # 通常最后一部分是产地/品牌
                        if len(parts) > 1:
                            item['品牌'] = parts[-1].strip()
                    # 处理斜杠
                    elif '/' in warehouse_origin:
                        parts = warehouse_origin.split('/')
                        if len(parts) > 1:
                            item['品牌'] = parts[1].strip()
                    # 处理空格 (如果既没有换行也没有斜杠，但有空格分隔)
                    elif ' ' in warehouse_origin:
                        parts = warehouse_origin.split()
                        if len(parts) > 1:
                            item['品牌'] = parts[-1].strip()

            elif len(cells) >= 7:
                 # 可能是某种缩略模式
                item['品名'] = cells[0]
                item['材质'] = cells[1]
                item['规格'] = cells[2]
                item['负差'] = cells[3].replace('-', '~')
                item['支/件'] = cells[4]
                item['支重(吨)'] = cells[5]
                item['可售量'] = cells[6]
                # 尝试从row_text找价格
                price_match = re.search(r'磅计\s*(\d{1,3}(,\d{3})*(\.\d+)?)', row_text)
                if price_match:
                     item['价格(元/吨)'] = price_match.group(1).replace(',', '')

            # 如果cells解析失败或为空，尝试使用split
            elif row_text:
                parts = row_text.split()
                if len(parts) >= 3:
                    item['品名'] = parts[0]
                    item['材质'] = parts[1]
                    item['规格'] = parts[2]
                    
                    if len(parts) >= 6:
                        item['负差'] = parts[3].replace('-', '~')
                        item['支/件'] = parts[4]
                        item['支重(吨)'] = parts[5]
                    
                    # 尝试从剩余部分提取价格
                    for part in parts:
                        if part.isdigit() and int(part) > 1000: # 假设价格大于1000
                             if not item['价格(元/吨)']:
                                 item['价格(元/吨)'] = part
            
            return item
            
        except Exception as e:
            logging.debug(f"解析行数据失败: {e}")
            return None
    
    def get_total_pages(self):
        """获取总页数"""
        try:
            # 尝试查找分页控件
            pagination_selectors = [
                ".el-pagination", ".ant-pagination", ".pagination"
            ]
            
            for selector in pagination_selectors:
                try:
                    pagination = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if pagination.is_displayed():
                        text = pagination.text
                        # 尝试匹配 "共 X 页" 或 "Total X"
                        match = re.search(r'(?:共|Total)\s*(\d+)\s*(?:页|pages?)', text)
                        if match:
                            return int(match.group(1))
                            
                        # 尝试查找最大的数字链接
                        items = pagination.find_elements(By.CSS_SELECTOR, "li.number, .ant-pagination-item")
                        max_page = 0
                        for item in items:
                            txt = item.text.strip()
                            if txt.isdigit():
                                max_page = max(max_page, int(txt))
                        
                        if max_page > 0:
                            return max_page
                except:
                    continue
            return 0
        except Exception as e:
            logging.warning(f"获取总页数失败: {e}")
            return 0

    def click_next_page(self):
        """点击下一页"""
        try:
            logging.info("尝试翻页...")
            # 滚动到底部以确保分页器可见
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)

            # 查找下一页按钮 - 增加更多选择器
            next_buttons = self.driver.find_elements(By.CSS_SELECTOR, 
                "button.btn-next, .el-pagination .btn-next, .ant-pagination-next, li.next, a.next")
            
            # 同时也尝试XPATH
            if not next_buttons:
                next_buttons = self.driver.find_elements(By.XPATH, 
                    "//button[contains(text(), '下一页') or contains(text(), 'Next') or @class='btn-next']")

            for btn in next_buttons:
                # 检查是否禁用
                if "disabled" in btn.get_attribute("class") or btn.get_attribute("disabled"):
                    continue
                    
                if btn.is_displayed():
                    try:
                        # 尝试点击
                        self.driver.execute_script("arguments[0].click();", btn)
                        # btn.click() # 普通点击有时会被遮挡
                        time.sleep(5)  # 等待页面加载
                        logging.info("已点击下一页")
                        return True
                    except Exception as e:
                        logging.warning(f"点击下一页按钮失败: {e}")
            
            # 尝试使用数字分页
            current_page = None
            # 查找当前激活的页码
            active_pages = self.driver.find_elements(By.CSS_SELECTOR, 
                ".el-pager li.active, .ant-pagination-item-active, .pagination .active")
            
            if active_pages:
                current_page = int(active_pages[0].text)
                logging.info(f"当前页码: {current_page}")
                
                # 尝试点击下一页数字
                next_page_num = current_page + 1
                next_page_elems = self.driver.find_elements(By.XPATH, 
                    f"//li[contains(@class, 'number') and text()='{next_page_num}'] | //a[text()='{next_page_num}']")
                
                if next_page_elems:
                    for elem in next_page_elems:
                        if elem.is_displayed():
                            self.driver.execute_script("arguments[0].click();", elem)
                            time.sleep(5)
                            logging.info(f"已点击第{next_page_num}页")
                            return True

            logging.warning("未找到可用的下一页按钮")
            return False
            
        except Exception as e:
            logging.error(f"点击下一页失败: {e}")
            return False
    
    def crawl(self, max_pages=None, skip_init=False, close_on_finish=True):
        """执行爬取"""
        try:
            if not skip_init:
                logging.info(f"开始访问网站: {self.url}")
                self.driver.get(self.url)
                
                # 等待页面加载
                self.wait_for_page_load()
                time.sleep(5)  # 额外等待
                
                # 如果需要登录
                self.login_if_needed()
            
            # 如果没有指定页数，询问用户
            if max_pages is None:
                try:
                    print("\n" + "="*50)
                    print("登录完成后，请输入要爬取的页数")
                    print("直接回车: 爬取直到没有下一页")
                    print("输入数字: 爬取指定页数")
                    print("="*50)
                    print("请输入页数: ", end="", flush=True)
                    import sys
                    user_input = sys.stdin.readline().strip()
                    if user_input.isdigit() and int(user_input) > 0:
                        max_pages = int(user_input)
                except:
                    pass

            total_pages = 0
            if max_pages:
                total_pages = max_pages
                logging.info(f"目标页数: {total_pages}")
            else:
                logging.info("未指定页数，将尝试自动翻页直到结束")
            
            all_data = []
            page = 1
            last_page_data_str = ""
            
            while True:
                # 检查是否超过总页数
                if total_pages > 0 and page > total_pages:
                    logging.info(f"已达到目标页数 {total_pages}，停止抓取")
                    break
                    
                logging.info(f"正在抓取第 {page} 页...")
                
                # 提取当前页数据
                page_data = self.extract_table_data()
                
                # 检查数据是否重复 (防止无限循环)
                current_page_data_str = str(page_data)
                if current_page_data_str == last_page_data_str:
                    logging.warning("当前页数据与上一页相同，可能已到达最后一页或翻页失败")
                    break
                last_page_data_str = current_page_data_str
                
                if page_data:
                    all_data.extend(page_data)
                    self.data = all_data  # 实时更新实例数据，以便中断时保存
                    logging.info(f"第 {page} 页提取到 {len(page_data)} 条数据")
                else:
                    logging.warning(f"第 {page} 页未提取到数据")
                    # 如果不是第一页且没有数据，停止抓取
                    if page > 1:
                        logging.info("当前页无数据，停止抓取")
                        break
                
                # 尝试点击下一页
                if not self.click_next_page():
                    logging.info("没有更多页面，停止抓取")
                    break
                
                page += 1
                time.sleep(2)  # 页面间延迟
            
            self.data = all_data
            logging.info(f"爬取完成，共获取 {len(all_data)} 条数据")
            
            return all_data
            
        except Exception as e:
            logging.error(f"爬取过程中出错: {e}")
            return []
        finally:
            if close_on_finish and hasattr(self, 'driver'):
                self.driver.quit()
                logging.info("浏览器已关闭")
    
    def save_data(self, filename=None):
        """保存数据"""
        if not self.data:
            logging.warning("没有数据可保存")
            return None
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"钢材市场数据_{timestamp}.xlsx"
        
        try:
            df = pd.DataFrame(self.data)
            df.to_excel(filename, index=False)
            logging.info(f"数据已保存到: {filename}")
            
            # 同时保存为CSV
            csv_filename = filename.replace('.xlsx', '.csv')
            df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
            logging.info(f"数据已保存到: {csv_filename}")
            
            return filename
            
        except Exception as e:
            logging.error(f"保存数据失败: {e}")
            return None
    
    def analyze_data(self):
        """分析数据"""
        if not self.data:
            logging.warning("没有数据可分析")
            return
        
        df = pd.DataFrame(self.data)
        
        print("\n" + "="*50)
        print("数据统计信息")
        print("="*50)
        print(f"总记录数: {len(df)}")
        
        # 显示前几条数据
        print("\n前10条数据:")
        print(df.head(10).to_string())
        
        # 如果有价格数据，进行统计
        if '价格(元/吨)' in df.columns:
            try:
                # 清理价格数据
                df['价格'] = df['价格(元/吨)'].str.extract(r'(\d+\.?\d*)')[0]
                df['价格'] = pd.to_numeric(df['价格'], errors='coerce')
                
                print(f"\n价格统计:")
                print(f"平均价格: {df['价格'].mean():.2f} 元/吨")
                print(f"最高价格: {df['价格'].max():.2f} 元/吨")
                print(f"最低价格: {df['价格'].min():.2f} 元/吨")
                print(f"价格中位数: {df['价格'].median():.2f} 元/吨")
            except:
                print("\n价格数据格式复杂，无法计算统计信息")

def main():
    """主函数"""
    print("钢材市场数据爬虫 v1.0")
    print("-" * 30)
    
    import sys
    
    # 默认参数
    headless = False
    
    # 尝试从命令行参数获取
    if len(sys.argv) > 1:
        if '--headless' in sys.argv:
            headless = True
    else:
        # 尝试交互式输入，如果环境支持
        try:
            if sys.stdin and sys.stdin.isatty():
                h = input("是否使用无头模式? (y/n, 默认n): ")
                if h.lower() == 'y': headless = True
        except:
            pass
            
    # 获取用户输入的页数
    max_pages = None
    # 移除了此处获取页数的逻辑，改为在登录后获取

    print(f"配置: 无头模式: {headless}")
    
    # 创建爬虫实例
    spider = XinggangSeleniumSpider(headless=headless)
    
    # 执行爬取
    data = spider.crawl(max_pages=max_pages)
    
    if data:
        # 保存数据
        spider.save_data()
        
        # 分析数据
        # spider.analyze_data()
    else:
        print("未能获取到数据，请检查:")
        print("1. 网站是否可以正常访问")
        print("2. 是否需要登录")
        print("3. 页面结构是否变化")
        
        # 询问是否查看页面截图
        try:
            if sys.stdin and sys.stdin.isatty():
                if input("是否查看页面截图? (y/n): ").lower() == 'y':
                    print("请查看当前目录下的 page_screenshot.png 和 page_source.html 文件")
            else:
                print("请查看当前目录下的 page_screenshot.png 和 page_source.html 文件")
        except:
            pass

if __name__ == "__main__":
    main()