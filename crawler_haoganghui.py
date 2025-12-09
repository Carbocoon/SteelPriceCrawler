import time
import pandas as pd
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import logging
import re

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

class HaoganghuiSpider:
    def __init__(self, headless=False, interactive=True):
        self.url = "https://www.haoganghui.cn/Main/cuohe_index"
        self.interactive = interactive
        self.data = []
        self.driver = None
        self.setup_driver(headless)
        
    def setup_driver(self, headless=False):
        """设置Chrome驱动"""
        try:
            chrome_options = Options()
            
            if headless:
                chrome_options.add_argument('--headless')
            
            # 添加常用参数
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-software-rasterizer') # 禁用软件光栅化
            chrome_options.add_argument('--log-level=3') # 禁用日志
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36')
            
            # 添加stealth.js避免被检测
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # 禁用图片加载，加快速度
            chrome_options.add_argument('--blink-settings=imagesEnabled=false')
            
            self.driver = webdriver.Chrome(options=chrome_options)
            logging.info("Chrome驱动初始化完成")
            
        except Exception as e:
            logging.error(f"驱动初始化失败: {e}")
            raise
    
    def wait_for_element(self, by, selector, timeout=30):
        """等待元素出现"""
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, selector))
            )
            return element
        except TimeoutException:
            logging.warning(f"等待元素超时: {selector}")
            return None
    
    def login_if_needed(self):
        """检查是否需要登录"""
        try:
            # 检查是否有登录提示
            time.sleep(3)
            
            # 检查是否有需要登录的提示
            login_elements = self.driver.find_elements(By.XPATH, 
                "//*[contains(text(), '登录') or contains(text(), 'Login') or contains(text(), '请登录')]")
            
            if login_elements:
                logging.warning("可能需要登录才能查看完整数据")
                if self.interactive:
                    print("\n" + "="*50)
                    print("提示：如果页面显示需要登录，请手动登录后继续")
                    print("="*50)
                    input("按回车键继续...")
                else:
                    logging.info("检测到可能需要登录，等待30秒供用户手动登录...")
                    time.sleep(30)
                
        except Exception as e:
            logging.debug(f"登录检查出错: {e}")
    
    def extract_table_data(self):
        """提取表格数据"""
        try:
            logging.info("正在定位表格数据...")
            
            # 等待表格加载
            time.sleep(5)
            
            # 尝试多种方式定位表格
            table_selectors = [
                "table",  # 标准表格
                "div.table",  # div实现的表格
                "div.data-table",  # 数据表格
                ".table-container",  # 表格容器
                ".data-container",  # 数据容器
                "[class*='table']",  # 包含table的类
                "[class*='data']",  # 包含data的类
                "#dataTable",  # ID为dataTable
                "#tableData",  # ID为tableData
            ]
            
            table = None
            for selector in table_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elements:
                        if elem.is_displayed() and (elem.tag_name == 'table' or 
                                                    'table' in elem.get_attribute('class') or
                                                    len(elem.text.split('\n')) > 5):
                            table = elem
                            logging.info(f"找到表格元素: {selector}")
                            break
                    if table:
                        break
                except Exception as e:
                    logging.debug(f"尝试选择器 {selector} 失败: {e}")
                    continue
            
            if not table:
                logging.warning("未找到明显的表格元素，尝试直接提取所有数据行")
                # 尝试直接查找数据行
                return self.extract_data_directly()
            
            # 获取表格所有行
            rows = []
            
            # 尝试不同的行选择器
            row_selectors = [
                "tr",  # 表格行
                "tbody tr",  # 表格体中的行
                "table tr",  # 表格中的行
                ".row",  # 行类
                "[class*='row']",  # 包含row的类
                ".data-row",  # 数据行
                "div.row",  # div行
            ]
            
            for selector in row_selectors:
                try:
                    if selector.startswith('tr'):
                        rows = table.find_elements(By.TAG_NAME, 'tr')
                    else:
                        rows = table.find_elements(By.CSS_SELECTOR, selector)
                    
                    if rows and len(rows) > 1:  # 至少有标题行和数据行
                        logging.info(f"使用选择器 {selector} 找到 {len(rows)} 行")
                        break
                except Exception as e:
                    logging.debug(f"尝试行选择器 {selector} 失败: {e}")
                    continue
            
            if not rows:
                # 最后尝试：直接查找页面中的所有行
                rows = self.driver.find_elements(By.CSS_SELECTOR, "tr, .row, [class*='row']")
                logging.info(f"直接查找找到 {len(rows)} 行")
            
            extracted_data = []
            
            for i, row in enumerate(rows):
                try:
                    row_text = row.text.strip()
                    
                    # 跳过空行和表头行（假设表头包含特定关键词）
                    if not row_text or len(row_text) < 10:
                        continue
                    
                    # 跳过明显的标题行
                    if any(keyword in row_text for keyword in ['品名', '材质', '规格', '价格', '库存', '表头', '标题']):
                        if i == 0:  # 如果是第一行，可能是表头
                            logging.info(f"跳过表头行: {row_text[:50]}...")
                            continue
                    
                    # 提取行数据
                    item = self.parse_row_data(row, row_text)
                    if item:
                        extracted_data.append(item)
                        logging.debug(f"解析成功第 {i+1} 行: {row_text[:50]}...")
                    
                except Exception as e:
                    logging.debug(f"处理第 {i+1} 行时出错: {e}")
                    continue
            
            logging.info(f"共提取 {len(extracted_data)} 条数据")
            return extracted_data
            
        except Exception as e:
            logging.error(f"提取表格数据失败: {e}")
            return []
    
    def extract_data_directly(self):
        """直接提取页面中的数据"""
        extracted_data = []
        
        try:
            # 获取整个页面的文本
            page_text = self.driver.find_element(By.TAG_NAME, 'body').text
            
            # 按行分割
            lines = page_text.split('\n')
            
            logging.info(f"页面共有 {len(lines)} 行文本")
            
            # 查找可能的数据行（包含钢材相关关键词）
            steel_keywords = ['螺纹钢', '线材', '热轧', '冷轧', '中厚板', '型钢', '钢管', '钢坯']
            
            for line in lines:
                line = line.strip()
                
                # 检查是否可能是数据行（包含数字和单位）
                if len(line) > 20 and any(char.isdigit() for char in line):
                    # 检查是否包含钢材关键词
                    if any(keyword in line for keyword in steel_keywords):
                        item = self.parse_text_line(line)
                        if item:
                            extracted_data.append(item)
            
            # 如果没有找到数据，尝试另一种方法：查找所有包含价格的文本块
            if not extracted_data:
                price_patterns = [
                    r'\d{3,5}\s*元/吨',
                    r'价格\s*[:：]\s*\d{3,5}',
                    r'¥\s*\d{3,5}',
                    r'\d{3,5}\s*元',
                ]
                
                for line in lines:
                    for pattern in price_patterns:
                        if re.search(pattern, line):
                            item = self.parse_text_line(line)
                            if item:
                                extracted_data.append(item)
                                break
            
        except Exception as e:
            logging.error(f"直接提取数据失败: {e}")
        
        return extracted_data
    
    def parse_row_data(self, row_element, row_text):
        """解析行数据"""
        try:
            # 创建数据项 - 只包含需要的字段
            item = {
                '品名': '',
                '品类': '',
                '材质': '',
                '规格': '',
                '负差': '',
                '支重': '',
                '长度': '',
                '支/件': '',
                '元/吨': '',
                '提货地': '',
            }
            
            # 尝试获取单元格数据
            cells = []
            
            # 尝试不同的单元格选择器
            cell_selectors = ['td', 'th', 'div.cell', 'span.cell', '.col', '[class*="col"]']
            
            for selector in cell_selectors:
                try:
                    cells = row_element.find_elements(By.CSS_SELECTOR, selector)
                    if cells:
                        break
                except:
                    continue
            
            # 如果没有找到标准单元格，尝试分割文本
            if cells:
                # 保留空单元格以维持索引对应关系
                cell_texts = [cell.text.strip() for cell in cells]
                
                # 根据用户提供的列顺序: 品名 品类 材质 规格 负差/支重 长度 支/件 件数 件重 元/吨 仓库
                if len(cell_texts) >= 11:
                    item['品名'] = cell_texts[0]
                    item['品类'] = cell_texts[1]
                    item['材质'] = cell_texts[2]
                    item['规格'] = cell_texts[3]
                    
                    # 处理 负差/支重 (索引4)
                    combined_val = cell_texts[4]
                    if '/' in combined_val:
                        parts = combined_val.split('/')
                        # 负差去掉正负号
                        item['负差'] = parts[0].replace('+', '').replace('-', '').strip()
                        if len(parts) > 1:
                            item['支重'] = parts[1].strip()
                    else:
                        # 如果没有斜杠，尝试直接赋值给负差(去掉符号)
                        item['负差'] = combined_val.replace('+', '').replace('-', '').strip()
                    
                    item['长度'] = cell_texts[5]
                    item['支/件'] = cell_texts[6]
                    # 跳过 件数(7) 和 件重(8)
                    item['元/吨'] = cell_texts[9]
                    # 只保留后四个字
                    if len(cell_texts[10].strip()) > 4:
                        item['提货地'] = cell_texts[10].strip()[-4:]
                    else:
                        item['提货地'] = cell_texts[10].strip()
                elif len(cell_texts) >= 10:
                    # 兼容旧格式或缺少仓库的情况
                    item['品名'] = cell_texts[0]
                    item['品类'] = cell_texts[1]
                    item['材质'] = cell_texts[2]
                    item['规格'] = cell_texts[3]
                    
                    # 处理 负差/支重
                    combined_val = cell_texts[4]
                    if '/' in combined_val:
                        parts = combined_val.split('/')
                        item['负差'] = parts[0].replace('+', '').replace('-', '').strip()
                        if len(parts) > 1:
                            item['支重'] = parts[1].strip()
                    else:
                        item['负差'] = combined_val.replace('+', '').replace('-', '').strip()

                    item['长度'] = cell_texts[5]
                    item['支/件'] = cell_texts[6]
                    item['元/吨'] = cell_texts[9]
            
            # 清理数据
            self.clean_data(item)
            
            # 如果完全没有提取到有效数据，返回None
            if not any(item[field] for field in ['品名', '材质', '规格', '元/吨']):
                return None
                
            return item
            
        except Exception as e:
            logging.debug(f"解析行数据失败: {e}")
            return None
    
    def parse_text_line(self, text_line):
        """解析文本行数据"""
        try:
            item = {
                '品名': '',
                '材质': '',
                '规格': '',
                '负差': '',
                '支/件': '',
                '支重(吨)': '',
                '可售量': '',
                '价格(元/吨)': '',
            }
            
            self.analyze_text_for_fields(item, text_line)
            self.clean_data(item)
            
            # 检查是否有足够的数据
            if item['品名'] or item['价格(元/吨)']:
                return item
            return None
            
        except Exception as e:
            logging.debug(f"解析文本行失败: {e}")
            return None
    
    def identify_field(self, item, text, index):
        """根据文本内容识别字段"""
        text_lower = text.lower()
        
        # 品名识别
        steel_names = ['螺纹钢', '线材', '圆钢', '角钢', '槽钢', '工字钢', 'h型钢', '热轧', '冷轧', '中厚板']
        if any(name in text for name in steel_names) and not item['品名']:
            item['品名'] = text
        
        # 规格识别 (通常包含×或*或x)
        if re.search(r'\d+[×*xX]\d+', text) and not item['规格']:
            item['规格'] = text
        
        # 材质识别 (通常包含字母和数字组合，如HRB400、Q235)
        if re.search(r'[A-Za-z]+\d+', text) and not item['材质']:
            item['材质'] = text
        
        # 价格识别
        price_match = re.search(r'(\d{3,5})\s*(?:元/吨|元|¥)', text)
        if price_match and not item['价格(元/吨)']:
            item['价格(元/吨)'] = price_match.group(1)
        
        # 可售量/库存识别
        stock_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:吨|件|支)', text)
        if stock_match and not item['可售量']:
            item['可售量'] = stock_match.group(1)
        
        # 支重识别
        weight_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:吨|t|kg)', text)
        if weight_match and not item['支重(吨)']:
            item['支重(吨)'] = weight_match.group(1)
        
        # 负差识别
        if any(keyword in text_lower for keyword in ['负差', '偏差', '公差']) and not item['负差']:
            # 尝试提取数字
            tolerance_match = re.search(r'([+-]?\d+(?:\.\d+)?)%?', text)
            if tolerance_match:
                item['负差'] = tolerance_match.group(1)
    
    def analyze_text_for_fields(self, item, text):
        """分析文本提取字段"""
        # 分割文本
        parts = re.split(r'\s+', text)
        
        # 尝试不同的分割方式
        for part in parts:
            self.identify_field(item, part, 0)
        
        # 如果还没有找到价格，尝试在整个文本中搜索
        if not item['价格(元/吨)']:
            price_patterns = [
                r'价格\s*[:：]\s*(\d{3,5})',
                r'(\d{3,5})\s*元/吨',
                r'¥\s*(\d{3,5})',
                r'(\d{3,5})\s*元',
            ]
            
            for pattern in price_patterns:
                match = re.search(pattern, text)
                if match:
                    item['价格(元/吨)'] = match.group(1)
                    break
    
    def clean_data(self, item):
        """清理数据"""
        # 清理价格字段
        if item.get('元/吨'):
            # 移除非数字字符
            price_clean = re.sub(r'[^\d\.]', '', item['元/吨'])
            if price_clean:
                item['元/吨'] = price_clean
        
        # 简单的空白清理
        for key in item:
            if item[key]:
                item[key] = item[key].strip()
    
    def get_total_pages(self):
        """获取总页数"""
        try:
            # 尝试查找分页控件
            pagination_selectors = [
                ".pagination", ".page", "[class*='paging']", "[class*='page']"
            ]
            
            for selector in pagination_selectors:
                try:
                    pagination = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if pagination.is_displayed():
                        text = pagination.text
                        # 尝试匹配 "共 X 页"
                        match = re.search(r'共\s*(\d+)\s*页', text)
                        if match:
                            return int(match.group(1))
                        
                        # 尝试匹配 "1/X"
                        match = re.search(r'1\s*/\s*(\d+)', text)
                        if match:
                            return int(match.group(1))
                            
                        # 尝试查找 "尾页" 按钮获取总页数
                        try:
                            last_page_btn = pagination.find_element(By.XPATH, 
                                ".//a[contains(text(), '尾页') or contains(text(), 'Last')]")
                            
                            # 尝试从 href 或 onclick 或 data 属性获取
                            href = last_page_btn.get_attribute('href')
                            if href:
                                match = re.search(r'[?&]p(?:age)?=(\d+)', href)
                                if match:
                                    return int(match.group(1))
                            
                            data_page = last_page_btn.get_attribute('data-page') or last_page_btn.get_attribute('data-p')
                            if data_page and data_page.isdigit():
                                return int(data_page)
                        except:
                            pass
                            
                        # 注意：不要简单地取最大数字链接，因为可能只显示了前几页 (如 1 2 3 4 5 ...)
                        # 除非我们确定这是最后一页
                except:
                    continue
            return 0
        except Exception as e:
            logging.warning(f"获取总页数失败: {e}")
            return 0

    def click_next_page(self):
        """点击下一页"""
        try:
            logging.info("尝试查找翻页控件...")
            
            # 滚动到底部
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # 尝试查找分页控件
            pagination_selectors = [
                ".pagination",  # 分页容器
                ".page",  # 分页
                "[class*='paging']",  # 包含paging的类
                "[class*='page']",  # 包含page的类
                ".next",  # 下一页
                ".btn-next",  # 下一页按钮
            ]
            
            for selector in pagination_selectors:
                try:
                    pagination = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if pagination.is_displayed():
                        logging.info(f"找到分页控件: {selector}")
                        
                        # 查找下一页按钮
                        # 更加健壮的查找逻辑
                        next_btn = None
                        
                        # 1. 尝试通过文本查找
                        links = pagination.find_elements(By.TAG_NAME, "a")
                        for link in links:
                            txt = link.text.strip()
                            # 匹配 "下一页", "Next", ">" (但不匹配 ">>")
                            if "下一页" in txt or "Next" in txt or txt == ">":
                                next_btn = link
                                break
                        
                        # 2. 尝试通过类名查找
                        if not next_btn:
                            next_btns = pagination.find_elements(By.CSS_SELECTOR, ".next, .btn-next, [class*='next']")
                            if next_btns:
                                next_btn = next_btns[0]
                        
                        if next_btn:
                            # 检查是否禁用
                            class_name = next_btn.get_attribute("class")
                            if class_name and ("disabled" in class_name or "disable" in class_name):
                                continue
                            
                            # 检查 disabled 属性
                            if next_btn.get_attribute("disabled"):
                                continue
                                
                            if next_btn.is_displayed() and next_btn.is_enabled():
                                # 滚动到按钮位置
                                self.driver.execute_script("arguments[0].scrollIntoView(true);", next_btn)
                                time.sleep(1)
                                
                                # 点击按钮
                                self.driver.execute_script("arguments[0].click();", next_btn)
                                time.sleep(5)
                                logging.info("已点击下一页")
                                return True
                except:
                    continue
            
            # 如果没找到分页控件，尝试查找页码链接
            try:
                # 查找当前页码
                current_page_elem = self.driver.find_element(By.CSS_SELECTOR, 
                    ".current, .active, [class*='active']")
                
                if current_page_elem:
                    current_page = current_page_elem.text
                    if current_page.isdigit():
                        next_page = int(current_page) + 1
                        
                        # 查找下一页链接
                        next_page_links = self.driver.find_elements(By.XPATH, 
                            f"//a[text()='{next_page}']")
                        
                        if next_page_links:
                            for link in next_page_links:
                                if link.is_displayed():
                                    self.driver.execute_script("arguments[0].click();", link)
                                    time.sleep(5)
                                    logging.info(f"已点击第{next_page}页")
                                    return True
            except:
                pass
            
            logging.warning("未找到下一页按钮或已经是最后一页")
            return False
            
        except Exception as e:
            logging.error(f"翻页失败: {e}")
            return False
    
    def crawl(self, max_pages=None, skip_init=False):
        """执行爬取"""
        try:
            if not skip_init:
                logging.info(f"开始访问网站: {self.url}")
                self.driver.get(self.url)
                
                # 等待页面加载
                time.sleep(10)  # 给予足够时间加载
                
                # 检查是否需要登录
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
                
                # 尝试翻页
                if not self.click_next_page():
                    logging.info("没有更多页面，停止抓取")
                    break
                
                page += 1
                time.sleep(3)  # 页面间延迟
            
            self.data = all_data
            logging.info(f"爬取完成，共获取 {len(all_data)} 条数据")
            
            return all_data
            
        except Exception as e:
            logging.error(f"爬取过程中出错: {e}")
            return []
    
    def save_data(self, filename=None):
        """保存数据"""
        if not self.data:
            logging.warning("没有数据可保存")
            return None
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"钢材数据_haoganghui_{timestamp}.xlsx"
        
        try:
            df = pd.DataFrame(self.data)
            
            # 定义列顺序
            columns_order = ['品名', '品类', '材质', '规格', '负差', '支重', '长度', '支/件', '元/吨', '提货地']
            
            # 只保留存在的列
            existing_columns = [col for col in columns_order if col in df.columns]
            
            # 按指定顺序排列列
            df = df[existing_columns]
            
            # 保存到Excel
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
        
        # 显示前10条数据
        print("\n前10条数据:")
        print(df.head(10).to_string())
        
        # 如果有价格数据，进行统计
        if '价格(元/吨)' in df.columns:
            try:
                # 清理价格数据并转换为数值
                df['价格_数值'] = pd.to_numeric(df['价格(元/吨)'], errors='coerce')
                df_clean = df.dropna(subset=['价格_数值'])
                
                if len(df_clean) > 0:
                    print(f"\n价格统计:")
                    print(f"有效价格记录数: {len(df_clean)}")
                    print(f"平均价格: {df_clean['价格_数值'].mean():.2f} 元/吨")
                    print(f"最高价格: {df_clean['价格_数值'].max():.2f} 元/吨")
                    print(f"最低价格: {df_clean['价格_数值'].min():.2f} 元/吨")
                    print(f"价格中位数: {df_clean['价格_数值'].median():.2f} 元/吨")
                
                # 按品名统计
                if '品名' in df.columns:
                    print(f"\n按品名统计记录数:")
                    name_counts = df['品名'].value_counts()
                    for name, count in name_counts.head(10).items():
                        print(f"  {name}: {count}条")
                    
            except Exception as e:
                logging.warning(f"价格统计失败: {e}")
        
        print(f"\n数据字段: {list(df.columns)}")
    
    def close(self):
        """关闭浏览器"""
        if self.driver:
            self.driver.quit()
            logging.info("浏览器已关闭")

def main():
    """主函数"""
    print("好钢汇钢材数据爬虫 v1.0")
    print("网站: https://www.haoganghui.cn/Main/cuohe_index")
    print("-" * 50)
    
    import sys
    import traceback
    
    # 默认参数
    headless = False
    
    # 从命令行参数获取
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            if arg == '--headless':
                headless = True
            elif arg == '--help' or arg == '-h':
                print("用法: python haoganghui_crawler.py [--headless]")
                print("示例: python haoganghui_crawler.py --headless")
                return
    
    # 获取用户输入的页数
    max_pages = None
    # 移除了此处获取页数的逻辑，改为在登录后获取

    print(f"配置: 无头模式: {headless}")
    print("提示: 如果是第一次运行，建议不使用无头模式，以便查看页面")
    print("-" * 50)
    
    spider = None
    try:
        # 创建爬虫实例
        spider = HaoganghuiSpider(headless=headless)
        
        # 执行爬取
        data = spider.crawl(max_pages=max_pages)
        
        if data:
            # 保存数据
            filename = spider.save_data()
            
            # 分析数据
            # spider.analyze_data()
            
            print(f"\n{'='*50}")
            print(f"爬取成功!")
            print(f"数据文件: {filename}")
            print(f"{'='*50}")
        else:
            print("\n未能获取到数据，可能原因:")
            print("1. 网站结构变化，需要调整选择器")
            print("2. 需要登录才能查看数据")
            print("3. 网络连接问题")
            print("4. 反爬虫机制阻止")
            print("\n已保存页面截图(haoganghui_screenshot.png)和源码(haoganghui_source.html)")
            print("请查看这些文件分析页面结构")
            
    except KeyboardInterrupt:
        print("\n用户中断爬取")
    except Exception as e:
        print(f"\n爬取过程中发生错误: {e}")
        traceback.print_exc()
    finally:
        if spider:
            spider.close()

if __name__ == "__main__":
    main()