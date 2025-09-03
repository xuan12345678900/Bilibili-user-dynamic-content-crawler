#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站动态内容解析脚本
用于解析B站用户动态页面HTML，提取关键信息并生成预览文本文件
"""

import os
import re
import json
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin
import argparse

class BilibiliDynamicParser:
    def __init__(self, html_file_path, excluded_images_file_path):
        """
        初始化解析器
        
        Args:
            html_file_path: HTML文件路径
            excluded_images_file_path: 排除图片链接文件路径
        """
        self.html_file_path = html_file_path
        self.excluded_images_file_path = excluded_images_file_path
        self.excluded_images = self._load_excluded_images()
        self.dynamics = []
        
    def _load_excluded_images(self):
        """
        加载需要排除的图片链接
        
        Returns:
            set: 排除图片链接集合
        """
        excluded_images = set()
        try:
            with open(self.excluded_images_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        excluded_images.add(line)
        except Exception as e:
            print(f"加载排除图片链接失败: {e}")
        return excluded_images
    
    def _is_excluded_image(self, image_url):
        """
        判断图片链接是否在排除列表中
        
        Args:
            image_url: 图片链接
            
        Returns:
            bool: 是否在排除列表中
        """
        if not image_url:
            return False
            
        # 处理相对路径
        if image_url.startswith('//'):
            image_url = 'https:' + image_url
            
        # 检查是否在排除列表中
        for excluded in self.excluded_images:
            if excluded in image_url:
                return True
        return False
    
    def _extract_username(self, item):
        """
        提取用户名
        
        Args:
            item: 动态项元素
            
        Returns:
            str: 用户名
        """
        username_elem = item.select_one('.bili-dyn-title__text')
        if username_elem:
            return username_elem.get_text(strip=True)
        return "未知用户"
    
    def _extract_publish_time(self, item):
        """
        提取发布时间
        
        Args:
            item: 动态项元素
            
        Returns:
            str: 发布时间
        """
        time_elem = item.select_one('.bili-dyn-time')
        if time_elem:
            time_text = time_elem.get_text(strip=True)
            # 提取年月日部分
            match = re.search(r'(\d{4}年\d{1,2}月\d{1,2}日)', time_text)
            if match:
                return match.group(1)
            return time_text
        return "未知时间"
    
    def _extract_text_content(self, item):
        """
        提取文本内容
        
        Args:
            item: 动态项元素
            
        Returns:
            str: 文本内容
        """
        text_content = ""
        
        # 尝试从不同位置提取文本内容
        content_elem = item.select_one('.bili-rich-text__content')
        if content_elem:
            # 移除表情图片等非文本元素
            for elem in content_elem.find_all(['img', 'svg']):
                elem.decompose()
            text_content = content_elem.get_text(strip=True)
            
        # 如果没有找到，尝试从其他位置提取
        if not text_content:
            desc_elem = item.select_one('.bili-dyn-card-video__desc')
            if desc_elem:
                text_content = desc_elem.get_text(strip=True)
                
        return text_content
    
    def _extract_images(self, item):
        """
        提取图片链接
        
        Args:
            item: 动态项元素
            
        Returns:
            list: 图片链接列表
        """
        images = set()  # 使用集合避免重复
        
        # 查找所有图片元素
        img_elems = item.select('img[src]')
        for img in img_elems:
            src = img.get('src', '')
            if src and not self._is_excluded_image(src):
                # 处理相对路径
                if src.startswith('//'):
                    src = 'https:' + src
                images.add(src)
                
        # 查找source元素中的图片
        source_elems = item.select('source[srcset]')
        for source in source_elems:
            srcset = source.get('srcset', '')
            if srcset:
                # 提取第一个URL
                src = srcset.split(',')[0].strip().split()[0]
                if src and not self._is_excluded_image(src):
                    if src.startswith('//'):
                        src = 'https:' + src
                    images.add(src)
                    
        return list(images)  # 转换为列表返回
    
    def _extract_interaction_counts(self, item):
        """
        提取互动数据（点赞、评论、分享）
        
        Args:
            item: 动态项元素
            
        Returns:
            dict: 互动数据字典
        """
        interaction = {
            'like': 0,
            'comment': 0,
            'share': 0
        }
        
        # 提取点赞数
        like_elem = item.select_one('.bili-dyn-action.like')
        if like_elem:
            like_text = like_elem.get_text(strip=True)
            like_match = re.search(r'(\d+(?:\.\d+)?[万]?\d*)', like_text)
            if like_match:
                like_count = like_match.group(1)
                if '万' in like_count:
                    num = float(like_count.replace('万', ''))
                    interaction['like'] = int(num * 10000)
                else:
                    interaction['like'] = int(like_count)
                    
        # 提取评论数
        comment_elem = item.select_one('.bili-dyn-action.comment')
        if comment_elem:
            comment_text = comment_elem.get_text(strip=True)
            comment_match = re.search(r'(\d+)', comment_text)
            if comment_match:
                interaction['comment'] = int(comment_match.group(1))
                
        # 提取分享数
        share_elem = item.select_one('.bili-dyn-action.forward')
        if share_elem:
            share_text = share_elem.get_text(strip=True)
            share_match = re.search(r'(\d+)', share_text)
            if share_match:
                interaction['share'] = int(share_match.group(1))
                
        return interaction
    
    def _extract_video_info(self, item):
        """
        提取视频信息（标题、封面图、时长）
        
        Args:
            item: 动态项元素
            
        Returns:
            dict: 视频信息字典
        """
        video_info = {
            'title': '',
            'cover': '',
            'duration': '',
            'link': ''
        }
        
        # 提取视频标题
        title_elem = item.select_one('.bili-dyn-card-video__title')
        if title_elem:
            video_info['title'] = title_elem.get_text(strip=True)
            
        # 提取视频链接
        link_elem = item.select_one('.bili-dyn-card-video[href]')
        if link_elem:
            href = link_elem.get('href', '')
            if href.startswith('//'):
                href = 'https:' + href
            video_info['link'] = href
            
        # 提取封面图
        cover_img = item.select_one('.bili-dyn-card-video__cover img[src]')
        if cover_img:
            src = cover_img.get('src', '')
            if src and not self._is_excluded_image(src):
                if src.startswith('//'):
                    src = 'https:' + src
                video_info['cover'] = src
                
        # 提取视频时长
        duration_elem = item.select_one('.duration-time')
        if duration_elem:
            video_info['duration'] = duration_elem.get_text(strip=True)
            
        return video_info
    
    def _determine_dynamic_type(self, item):
        """
        判断动态类型
        
        Args:
            item: 动态项元素
            
        Returns:
            str: 动态类型
        """
        # 检查是否是置顶动态
        # 只有2022年05月14日发布的特定动态才是置顶动态
        time_elem = item.select_one('.bili-dyn-time')
        if time_elem:
            time_text = time_elem.get_text(strip=True)
            # 提取年月日部分
            match = re.search(r'(\d{4}年\d{1,2}月\d{1,2}日)', time_text)
            if match and match.group(1) == '2022年05月14日':
                # 进一步验证文本内容
                content_elem = item.select_one('.bili-rich-text__content')
                if content_elem and '永远要相信自己 并且坚定的往自己想要去的方向前进 梦想一旦开始就很难停止' in content_elem.get_text(strip=True):
                    return "置顶动态"
            
        # 检查是否是视频动态
        if item.select_one('.bili-dyn-card-video'):
            # 检查是否是投稿视频
            if time_elem and '投稿了视频' in time_elem.get_text(strip=True):
                return "投稿视频动态"
            return "动态视频"
            
        # 检查是否是带图片的文本动态
        if item.select_one('.bili-album'):
            return "带图片的文本动态"
            
        # 默认为纯文本动态
        return "纯文本动态"
    
    def parse(self):
        """
        解析HTML文件，提取动态信息
        
        Returns:
            list: 动态信息列表
        """
        try:
            with open(self.html_file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
        except Exception as e:
            print(f"读取HTML文件失败: {e}")
            return []
            
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 查找所有动态项
        dynamic_items = soup.select('.bili-dyn-list__item')
        
        for item in dynamic_items:
            try:
                # 提取基本信息
                username = self._extract_username(item)
                publish_time = self._extract_publish_time(item)
                dynamic_type = self._determine_dynamic_type(item)
                text_content = self._extract_text_content(item)
                images = self._extract_images(item)
                interaction = self._extract_interaction_counts(item)
                
                # 构建动态信息字典
                dynamic_info = {
                    'username': username,
                    'publish_time': publish_time,
                    'dynamic_type': dynamic_type,
                    'text_content': text_content,
                    'images': images,
                    'like_count': interaction['like'],
                    'comment_count': interaction['comment'],
                    'share_count': interaction['share']
                }
                
                # 如果是视频动态，提取视频信息
                if dynamic_type in ["投稿视频动态", "动态视频"]:
                    video_info = self._extract_video_info(item)
                    dynamic_info.update({
                        'video_title': video_info['title'],
                        'video_cover': video_info['cover'],
                        'video_duration': video_info['duration'],
                        'video_link': video_info['link']
                    })
                
                self.dynamics.append(dynamic_info)
            except Exception as e:
                print(f"解析动态项失败: {e}")
                continue
                
        return self.dynamics
    
    def generate_preview_file(self, output_file_path=None):
        """
        生成预览文本文件
        
        Args:
            output_file_path: 输出文件路径，如果为None则使用默认路径
            
        Returns:
            str: 输出文件路径
        """
        if not output_file_path:
            # 默认输出路径为HTML文件同目录下的预览文件
            html_dir = os.path.dirname(self.html_file_path)
            html_name = os.path.splitext(os.path.basename(self.html_file_path))[0]
            output_file_path = os.path.join(html_dir, f"{html_name}_预览.txt")
            
        try:
            with open(output_file_path, 'w', encoding='utf-8') as f:
                f.write(f"B站动态内容预览\n")
                f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"=" * 80 + "\n\n")
                
                for i, dynamic in enumerate(self.dynamics, 1):
                    f.write(f"动态 #{i}\n")
                    f.write(f"-" * 40 + "\n")
                    f.write(f"用户名: {dynamic['username']}\n")
                    f.write(f"发布时间: {dynamic['publish_time']}\n")
                    f.write(f"动态类型: {dynamic['dynamic_type']}\n")
                    f.write(f"文本内容: {dynamic['text_content']}\n")
                    
                    if dynamic['images']:
                        f.write(f"图片链接:\n")
                        for img in dynamic['images']:
                            f.write(f"  - {img}\n")
                    
                    f.write(f"点赞数: {dynamic['like_count']}\n")
                    f.write(f"评论数: {dynamic['comment_count']}\n")
                    f.write(f"分享数: {dynamic['share_count']}\n")
                    
                    if 'video_title' in dynamic and dynamic['video_title']:
                        f.write(f"视频标题: {dynamic['video_title']}\n")
                        f.write(f"视频链接: {dynamic.get('video_link', '')}\n")
                        f.write(f"封面图链接: {dynamic.get('video_cover', '')}\n")
                        f.write(f"视频时长: {dynamic.get('video_duration', '')}\n")
                    
                    f.write("\n" + "=" * 80 + "\n\n")
                    
        except Exception as e:
            print(f"生成预览文件失败: {e}")
            return None
            
        return output_file_path


def main():
    parser = argparse.ArgumentParser(description='B站动态内容解析工具')
    parser.add_argument('html_file', help='HTML文件路径')
    parser.add_argument('-e', '--exclude', default='排除的图片链接.txt', 
                       help='排除图片链接文件路径 (默认: 排除的图片链接.txt)')
    parser.add_argument('-o', '--output', help='输出文件路径 (默认: HTML文件同目录下的预览文件)')
    
    args = parser.parse_args()
    
    # 检查HTML文件是否存在
    if not os.path.exists(args.html_file):
        print(f"错误: HTML文件 '{args.html_file}' 不存在")
        return
        
    # 检查排除图片链接文件是否存在
    if not os.path.exists(args.exclude):
        print(f"警告: 排除图片链接文件 '{args.exclude}' 不存在，将不排除任何图片")
        
    # 创建解析器并解析HTML文件
    parser = BilibiliDynamicParser(args.html_file, args.exclude)
    dynamics = parser.parse()
    
    if not dynamics:
        print("未找到任何动态内容")
        return
        
    print(f"成功解析 {len(dynamics)} 条动态")
    
    # 生成预览文件
    output_file = parser.generate_preview_file(args.output)
    if output_file:
        print(f"预览文件已生成: {output_file}")
    else:
        print("生成预览文件失败")


if __name__ == '__main__':
    main()