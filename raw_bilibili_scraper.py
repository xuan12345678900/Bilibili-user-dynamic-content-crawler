#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站动态原始数据爬虫
直接保存页面原始HTML内容，不进行任何数据处理
"""

import time
import json
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException

class RawBilibiliScraper:
    def __init__(self):
        self.raw_html_data = []
        
        # Chrome配置
        self.chrome_options = Options()
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--disable-dev-shm-usage')
        self.chrome_options.add_argument('--start-maximized')
        self.chrome_options.add_experimental_option("detach", True)
        
    def init_driver(self):
        """初始化Chrome浏览器驱动"""
        try:
            from selenium import webdriver
            from webdriver_manager.chrome import ChromeDriverManager
            from selenium.webdriver.chrome.service import Service
            
            # 使用webdriver-manager自动管理ChromeDriver
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=self.chrome_options)
            
            # 设置隐式等待
            driver.implicitly_wait(10)
            
            return driver
            
        except Exception as e:
            print(f"❌ 浏览器初始化失败: {e}")
            print("请确保：")
            print("1. 已安装Chrome浏览器")
            print("2. 网络连接正常")
            print("3. 防火墙允许ChromeDriver")
            raise e
    
    def scrape_raw(self, uid, mode='traditional'):
        """原始数据爬取方法 - 支持三种模式
        
        Args:
            uid: 用户UID
            mode: 'traditional'(传统模式) 或 'fast'(快速模式) 或 'manual'(半自动模式)
        """
        
        if mode == 'fast':
            return self._scrape_fast_mode(uid)
        elif mode == 'manual':
            return self._scrape_manual_mode(uid)
            
        print(f"🚀 开始爬取UID: {uid} 的原始动态数据")
        print("将自动滚动直到到达最早动态或检测到'你已经到达世界的尽头'")
        
        driver = None
        try:
            # 启动浏览器
            driver = self.init_driver()
            
            # 访问动态页面
            url = f"https://space.bilibili.com/{uid}/dynamic"
            driver.get(url)
            
            # 等待页面加载
            WebDriverWait(driver, 15).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            
            # 等待动态内容加载
            WebDriverWait(driver, 15).until(
                lambda d: d.find_elements(By.CSS_SELECTOR, ".bili-dyn-item, [data-did]")
            )
            
            # 获取用户名
            try:
                # 首先尝试从页面元素获取用户名
                username_element = driver.find_element(By.CSS_SELECTOR, ".h-name, .n-name")
                username = username_element.text.strip()
                print(f"📝 目标用户: {username}")
            except:
                try:
                    # 如果无法从元素获取，尝试从页面标题提取
                    page_title = driver.title
                    # 标题格式通常是"用户名个人动态-用户名动态记录-哔哩哔哩视频"
                    if "个人动态-" in page_title:
                        username = page_title.split("个人动态-")[0]
                        print(f"📝 从标题提取用户名: {username}")
                    else:
                        username = f"用户{uid}"
                        print("⚠️ 无法从标题提取用户名")
                except:
                    username = f"用户{uid}"
                    print("⚠️ 无法获取用户名")
            
            print("🔄 开始滚动加载动态...")
            
            scroll_count = 0
            last_height = 0
            no_new_content_count = 0
            
            # 优化：智能等待参数
            max_wait_time = 8  # 最大等待时间
            check_interval = 0.3  # 检查间隔
            
            while True:
                # 快速检查是否到达世界尽头
                try:
                    end_text = driver.find_elements(By.XPATH, "//*[contains(text(), '你已经到达世界的尽头')]")
                    if end_text:
                        print("🏁 检测到'你已经到达世界的尽头'，停止爬取")
                        break
                except:
                    pass
                
                # 快速检查是否有"暂无动态"提示
                try:
                    no_dynamic = driver.find_elements(By.XPATH, "//*[contains(text(), '暂无动态')]")
                    if no_dynamic:
                        print("⚠️ 该用户暂无动态")
                        break
                except:
                    pass
                
                # 获取当前动态数量
                current_count = driver.execute_script(
                    "return document.querySelectorAll('.bili-dyn-item, [data-did]').length"
                )
                print(f"📊 当前已加载 {current_count} 条动态")
                
                # 滚动到页面底部
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                
                # 优化：智能等待新内容加载
                start_wait = time.time()
                new_height = last_height
                
                while time.time() - start_wait < max_wait_time:
                    new_height = driver.execute_script("return document.body.scrollHeight")
                    current_dynamics = driver.execute_script(
                        "return document.querySelectorAll('.bili-dyn-item, [data-did]').length"
                    )
                    
                    # 检查是否有新内容
                    if new_height > last_height or current_dynamics > current_count:
                        no_new_content_count = 0
                        print(f"✅ 新内容已加载 (耗时 {time.time() - start_wait:.1f}s)")
                        break
                    
                    # 检查是否到达世界尽头（在加载过程中）
                    try:
                        end_text = driver.find_elements(By.XPATH, "//*[contains(text(), '你已经到达世界的尽头')]")
                        if end_text:
                            print("🏁 检测到到达世界尽头")
                            break
                    except:
                        pass
                    
                    time.sleep(check_interval)
                else:
                    # 等待超时，可能没有新内容
                    no_new_content_count += 1
                    print(f"⏳ 未检测到新内容 ({no_new_content_count}/3)")
                    
                    # 如果连续3次都没有新内容，确认加载完毕
                    if no_new_content_count >= 3:
                        # 最终检查是否到底
                        final_check = driver.execute_script(
                            "return document.querySelectorAll('.bili-dyn-item, [data-did]').length"
                        )
                        if final_check == current_count:
                            print("✅ 确认已加载所有动态内容")
                            break
                
                last_height = new_height
                scroll_count += 1
                
                # 每滚动10次，动态调整等待策略
                if scroll_count % 10 == 0:
                    print(f"🔄 已滚动 {scroll_count} 次，继续加载...")
                    # 根据加载速度调整下次等待时间
                    if no_new_content_count == 0:
                        max_wait_time = max(3, max_wait_time - 0.5)  # 加快
                    else:
                        max_wait_time = min(12, max_wait_time + 1)  # 减慢
                time.sleep(2)
                
                # 等待新内容加载
                try:
                    WebDriverWait(driver, 10).until(
                        lambda d: d.execute_script("return document.body.scrollHeight") > last_height
                    )
                    no_new_content_count = 0
                except:
                    # 如果没有新内容，增加计数器
                    no_new_content_count += 1
                    print(f"⏳ 等待新内容加载... ({no_new_content_count}/3)")
                    
                    # 如果连续3次都没有新内容，认为已经加载完毕
                    if no_new_content_count >= 3:
                        print("✅ 已加载所有动态内容")
                        break
                
                new_height = driver.execute_script("return document.body.scrollHeight")
                
                # 如果页面高度没有变化，检查是否真的到底了
                if new_height == last_height:
                    # 再次检查是否到达世界尽头
                    try:
                        end_text = driver.find_elements(By.XPATH, "//*[contains(text(), '你已经到达世界的尽头')]")
                        if end_text:
                            print("🏁 确认到达世界尽头")
                            break
                    except:
                        pass
                
                last_height = new_height
                scroll_count += 1
                
                # 每滚动10次暂停一下
                if scroll_count % 10 == 0:
                    print(f"🔄 已滚动 {scroll_count} 次，继续加载...")
                    time.sleep(3)
            
            # 直接获取页面原始HTML内容
            self.extract_raw_html(driver)
            
        except Exception as e:
            print(f"❌ 爬取失败: {e}")
        finally:
            print(f"✅ 已爬取 {len(self.raw_html_data)} 条原始动态")
            if driver:
                driver.quit()
            return self.raw_html_data
    
    def _scrape_fast_mode(self, uid):
        """快速模式：一次性滚动到页面底部"""
        
        print(f"⚡ 快速模式 - 开始爬取UID: {uid}")
        print("将一次性滚动到底部获取所有动态")
        
        driver = None
        start_time = time.time()
        
        try:
            # 启动浏览器
            driver = self.init_driver()
            
            # 访问动态页面
            url = f"https://space.bilibili.com/{uid}/dynamic"
            driver.get(url)
            
            # 等待页面完全加载
            from selenium.webdriver.support.ui import WebDriverWait
            WebDriverWait(driver, 15).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            
            # 等待初始动态加载
            WebDriverWait(driver, 15).until(
                lambda d: d.find_elements("css selector", ".bili-dyn-item, [data-did]")
            )

            # 获取用户名
            try:
                # 首先尝试从页面元素获取用户名
                username = driver.find_element("css selector", ".h-name, .n-name").text.strip()
                print(f"📝 目标用户: {username}")
            except:
                try:
                    # 如果无法从元素获取，尝试从页面标题提取
                    page_title = driver.title
                    # 标题格式通常是"用户名个人动态-用户名动态记录-哔哩哔哩视频"
                    if "个人动态-" in page_title:
                        username = page_title.split("个人动态-")[0]
                        print(f"📝 从标题提取用户名: {username}")
                    else:
                        username = f"用户{uid}"
                        print("⚠️ 无法从标题提取用户名")
                except:
                    username = f"用户{uid}"
                    print("⚠️ 无法获取用户名")
            
            # 快速模式：智能滚动到底部
            print("⚡ 开始智能滚动...")
            
            max_scroll_attempts = 20  # 减少滚动次数，增加等待时间
            scroll_count = 0
            total_dynamics = 0
            
            while scroll_count < max_scroll_attempts:
                # 获取当前动态数量
                current_dynamics = driver.execute_script(
                    "return document.querySelectorAll('.bili-dyn-item, [data-did]').length"
                )
                
                # 检查是否到达底部
                end_text = driver.execute_script(
                    "return document.querySelector('*[class*=\"end\"], *[class*=\"no-more\"]') !== null"
                )
                
                # 检查"你已经到达世界的尽头"
                end_message = driver.execute_script(
                    "return Array.from(document.querySelectorAll('*')).some(el => el.textContent.includes('你已经到达世界的尽头'))"
                )
                
                if end_text or end_message:
                    print("🏁 已到达底部")
                    break
                
                # 记录上一次的高度
                last_height = driver.execute_script("return document.body.scrollHeight")
                
                # 快速滚动到底部
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                
                # 等待新内容加载（增加等待时间）
                time.sleep(2.5)
                
                # 检查是否有新内容
                new_height = driver.execute_script("return document.body.scrollHeight")
                new_dynamics = driver.execute_script(
                    "return document.querySelectorAll('.bili-dyn-item, [data-did]').length"
                )
                
                # 如果高度和动态数量都没有变化，认为已加载完成
                if new_height == last_height and new_dynamics == current_dynamics:
                    # 再等待一下，确保内容加载完成
                    time.sleep(3)
                    final_height = driver.execute_script("return document.body.scrollHeight")
                    final_dynamics = driver.execute_script(
                        "return document.querySelectorAll('.bili-dyn-item, [data-did]').length"
                    )
                    
                    if final_height == new_height and final_dynamics == new_dynamics:
                        print("✅ 确认已加载所有动态")
                        break
                
                total_dynamics = new_dynamics
                scroll_count += 1
                
                if scroll_count % 5 == 0:
                    print(f"🔄 已快速滚动 {scroll_count} 次，当前 {total_dynamics} 条动态")
            
            # 额外等待确保所有内容加载完成
            print("等待内容完全加载...")
            time.sleep(3)
            
            # 提取原始HTML数据
            self.extract_raw_html(driver)
            
            elapsed = time.time() - start_time
            print(f"✅ 传统模式完成！耗时 {elapsed:.1f}秒")
            
            # 计算并显示实际动态数量
            if self.raw_html_data and "page_html" in self.raw_html_data[0]:
                try:
                    import re
                    page_html = self.raw_html_data[0]["page_html"]
                    # 使用更精确的正则表达式匹配动态容器
                    # 匹配实际的HTML结构：<div class="bili-dyn-list__item"><div class="bili-dyn-item">
                    pattern = r'<div class="bili-dyn-list__item"><div class="bili-dyn-item">'
                    matches = re.findall(pattern, page_html)
                    actual_count = len(matches)
                    print(f"📊 共获取 {actual_count} 条原始动态")
                except Exception as e:
                    print(f"⚠️ 计算动态数量时出错: {e}")
            else:
                print(f"📊 共获取 {len(self.raw_html_data)} 条原始动态")
            
            return self.raw_html_data
            
        except Exception as e:
            print(f"❌ 快速模式失败: {e}")
            return []
        finally:
            if driver:
                driver.quit()

    def _scrape_manual_mode(self, uid):
        """半自动模式：手动滚动后一次性提取数据"""
        start_time = time.time()
        driver = None
        
        try:
            driver = self.init_driver()
            url = f"https://space.bilibili.com/{uid}/dynamic"
            driver.get(url)
            
            print(f"🎯 半自动模式启动")
            print(f"🌐 正在打开: {url}")
            print("=" * 60)
            
            # 等待页面初始加载
            time.sleep(3)
            
            # 获取用户名
            try:
                # 首先尝试从页面元素获取用户名
                username_element = driver.find_element(By.CSS_SELECTOR, '.h-name, .user-name, [class*="name"]')
                username = username_element.text.strip()
                print(f"👤 目标用户: {username} (UID: {uid})")
            except:
                try:
                    # 如果无法从元素获取，尝试从页面标题提取
                    page_title = driver.title
                    # 标题格式通常是"用户名个人动态-用户名动态记录-哔哩哔哩视频"
                    if "个人动态-" in page_title:
                        username = page_title.split("个人动态-")[0]
                        print(f"👤 从标题提取用户名: {username} (UID: {uid})")
                    else:
                        username = f"用户_{uid}"
                        print(f"⚠️ 无法从标题提取用户名，使用UID: {uid}")
                except:
                    username = f"用户_{uid}"
                    print(f"⚠️ 无法获取用户名，使用UID: {uid}")
            
            print("\n" + "=" * 60)
            print("🎮 半自动模式使用说明:")
            print("1. 浏览器已打开，请手动滚动页面到底部")
            print("2. 确保所有动态内容都已加载完成")
            print("3. 按回车键开始提取数据")
            print("4. 如需取消，请关闭浏览器窗口")
            print("=" * 60)
            
            # 等待用户确认
            input("\n📋 请确认已滚动到底部，然后按回车键开始提取...")
            
            print("🔄 正在提取原始HTML数据...")
            self.extract_raw_html(driver)
            
            elapsed = time.time() - start_time
            print(f"✅ 半自动模式完成！耗时 {elapsed:.1f}秒")
            
            # 计算并显示实际动态数量
            if self.raw_html_data and "page_html" in self.raw_html_data[0]:
                try:
                    import re
                    page_html = self.raw_html_data[0]["page_html"]
                    # 使用更精确的正则表达式匹配动态容器
                    pattern = r'<div class="bili-dyn-list__item"><div class="bili-dyn-item">'
                    matches = re.findall(pattern, page_html)
                    actual_count = len(matches)
                    print(f"📊 共获取 {actual_count} 条原始动态")
                except Exception as e:
                    print(f"⚠️ 计算动态数量时出错: {e}")
            else:
                print(f"📊 共获取 {len(self.raw_html_data)} 条原始动态")
            
            return self.raw_html_data
            
        except Exception as e:
            print(f"❌ 半自动模式失败: {e}")
            return []
        finally:
            if driver:
                driver.quit()
    
    def extract_raw_html(self, driver):
        """直接提取页面原始HTML内容，不进行任何处理"""
        
        # 等待页面完全加载
        time.sleep(2)
        
        try:
            # 直接获取整个页面的HTML内容
            page_html = driver.page_source
            
            # 获取页面URL作为标识
            page_url = driver.current_url
            
            # 获取当前时间戳
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 创建原始数据对象
            raw_data = {
                "timestamp": timestamp,
                "url": page_url,
                "page_html": page_html,
                "extraction_time": time.time()
            }
            
            self.raw_html_data.append(raw_data)
            print(f"成功获取页面原始HTML内容，大小: {len(page_html)} 字符")
            
            # 计算并显示实际动态数量
            try:
                import re
                # 使用正则表达式计算实际动态数量
                # 匹配实际的HTML结构：<div class="bili-dyn-list__item"><div class="bili-dyn-item">
                pattern = r'<div class="bili-dyn-list__item"><div class="bili-dyn-item">'
                matches = re.findall(pattern, page_html)
                actual_count = len(matches)
                print(f"📊 检测到 {actual_count} 条动态内容")
            except Exception as e:
                print(f"⚠️ 计算动态数量时出错: {e}")
            
        except Exception as e:
            print(f"获取原始HTML失败: {e}")
    
    def save_raw_data(self, uid, username):
        """保存原始HTML数据"""
        if not self.raw_html_data:
            print("没有数据需要保存")
            return
        
        # 创建输出目录
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_dir = f"{username}_原始数据_{timestamp}"
        os.makedirs(output_dir, exist_ok=True)
        
        # 保存原始HTML数据
        html_filename = os.path.join(output_dir, f"{username}_原始页面HTML.html")
        with open(html_filename, 'w', encoding='utf-8') as f:
            f.write(self.raw_html_data[0]["page_html"])
        
        # 保存元数据
        metadata_filename = os.path.join(output_dir, f"{username}_原始数据元数据.json")
        with open(metadata_filename, 'w', encoding='utf-8') as f:
            json.dump({
                "uid": uid,
                "username": username,
                "timestamp": timestamp,
                "extraction_time": self.raw_html_data[0]["extraction_time"],
                "url": self.raw_html_data[0]["url"],
                "html_size": len(self.raw_html_data[0]["page_html"])
            }, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 原始数据已保存到目录: {output_dir}")
        print(f"📄 原始HTML: {html_filename}")
        print(f"📊 元数据: {metadata_filename}")

def main():
    print("=== 原始版B站动态爬虫 ===")
    print("直接保存页面原始HTML内容，不进行任何数据处理")
    print()
    
    scraper = RawBilibiliScraper()
    
    # 支持自定义UID
    uid = input("请输入B站用户UID (默认: 618107325): ").strip()
    if not uid:
        uid = "618107325"
    
    # 选择爬取模式
    print("请选择爬取模式:")
    print("1. 传统模式 - 智能滚动加载，适合大多数情况")
    print("2. 快速模式 - 一次性滚动到底部，速度更快")
    print("3. 半自动模式 - 手动滚动页面后提取数据")
    mode_input = input("请输入模式序号 (默认: 3): ").strip()
    
    if mode_input == "1":
        mode = 'traditional'
    elif mode_input == "2":
        mode = 'fast'
    elif mode_input == "3" or not mode_input:
        mode = 'manual'
    else:
        print("无效输入，使用默认半自动模式")
        mode = 'manual'
    
    print(f"\n开始爬取用户 UID: {uid}")
    print(f"爬取模式: {mode}")
    print("=" * 50)
    
    try:
        data = scraper.scrape_raw(uid, mode)
        if data:
            # 计算并显示实际动态数量
            actual_count = 0
            if data and "page_html" in data[0]:
                try:
                    import re
                    page_html = data[0]["page_html"]
                    # 使用更精确的正则表达式匹配动态容器
                    # 匹配实际的HTML结构：<div class="bili-dyn-list__item"><div class="bili-dyn-item">
                    pattern = r'<div class="bili-dyn-list__item"><div class="bili-dyn-item">'
                    matches = re.findall(pattern, page_html)
                    actual_count = len(matches)
                except Exception as e:
                    print(f"⚠️ 计算动态数量时出错: {e}")
                    actual_count = len(data)
            else:
                actual_count = len(data)
                
            print(f"\n✅ 爬取完成！共获取 {actual_count} 条原始动态数据")
            
            # 获取用户名（从HTML中提取）
            username = "未知用户"
            if data and len(data) > 0 and "page_html" in data[0]:
                html_content = data[0]["page_html"]
                # 尝试从HTML标题中提取用户名
                try:
                    import re
                    # 从HTML标题中提取用户名，标题格式通常是"用户名个人动态-用户名动态记录-哔哩哔哩视频"
                    title_match = re.search(r'<title>(.+?)个人动态-', html_content)
                    if title_match:
                        username = title_match.group(1)
                        print(f"📝 从HTML提取用户名: {username}")
                    else:
                        print("⚠️ 无法从HTML提取用户名")
                except:
                    print("⚠️ 提取用户名时出错")
            
            # 保存原始数据
            scraper.save_raw_data(uid, username)
        else:
            print("\n⚠️ 未获取到任何动态数据")
    except KeyboardInterrupt:
        print("\n❌ 用户中断操作")
    except Exception as e:
        print(f"\n❌ 爬取过程出错: {e}")

if __name__ == "__main__":
    main()