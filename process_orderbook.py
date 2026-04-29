"""
处理OKX orderbook数据
将每个snapshot和update处理成包含以下字段的总结行:
ts, best_bid, best_bid_size, best_ask, best_ask_size, mid, spread
"""

import json
import tarfile
from pathlib import Path
from typing import Dict, Optional, Tuple
import csv
import io


class OrderbookProcessor:
    """处理 orderbook 数据的类"""
    
    def __init__(self, output_root: Path):
        self.output_root = output_root
        self.output_root.mkdir(exist_ok=True)
        
    def process_all_files(self, source_root: Path):
        """处理源目录中的所有tar.gz文件，保持目录结构"""
        
        tar_files = sorted(source_root.glob("*.tar.gz"))
        print(f"找到 {len(tar_files)} 个tar.gz文件")
        
        for i, tar_file in enumerate(tar_files, 1):
            print(f"\n[{i}/{len(tar_files)}] 处理: {tar_file.name}")
            self.process_tar_file(tar_file)
    
    def process_tar_file(self, tar_path: Path):
        """处理单个tar.gz文件"""
        
        # 创建输出文件路径
        output_file = self.output_root / tar_path.stem  # 移除.tar.gz后缀
        output_file = output_file.with_suffix('.csv')  # 加上.csv后缀
        
        try:
            with tarfile.open(tar_path, "r:gz") as tar:
                members = sorted([m for m in tar.getmembers() if m.isfile()], 
                               key=lambda m: m.name)
                
                if not members:
                    print(f"  警告: 没有找到文件成员")
                    return
                
                # 通常只有一个成员文件，包含所有的JSON行
                for member in members:
                    fobj = tar.extractfile(member)
                    if fobj is None:
                        continue
                    
                    # 使用流式处理，逐行处理并直接写入
                    output_file.parent.mkdir(parents=True, exist_ok=True)
                    
                    fieldnames = ['ts', 'best_bid', 'best_bid_size', 'best_ask', 
                                 'best_ask_size', 'mid', 'spread']
                    
                    with open(output_file, 'w', newline='', encoding='utf-8') as csv_f:
                        writer = csv.DictWriter(csv_f, fieldnames=fieldnames)
                        writer.writeheader()
                        
                        # 初始化盘口状态
                        current_asks: Dict[str, float] = {}  # price -> size (float)
                        current_bids: Dict[str, float] = {}  # price -> size (float)
                        
                        line_count = 0
                        output_count = 0
                        
                        for line in fobj:
                            line_count += 1
                            
                            try:
                                data = json.loads(line)
                                action = data.get('action')
                                ts = data.get('ts')
                                
                                if action == 'snapshot':
                                    # 重置盘口
                                    current_asks.clear()
                                    current_bids.clear()
                                    
                                    # 加载snapshot数据
                                    for data_item in data.get('data', []):
                                        for ask_data in data_item.get('asks', []):
                                            price, size_str, _ = ask_data
                                            size = float(size_str)
                                            if size > 0:
                                                current_asks[price] = size
                                            else:
                                                current_asks.pop(price, None)
                                        
                                        for bid_data in data_item.get('bids', []):
                                            price, size_str, _ = bid_data
                                            size = float(size_str)
                                            if size > 0:
                                                current_bids[price] = size
                                            else:
                                                current_bids.pop(price, None)
                                
                                elif action == 'update':
                                    # 更新盘口
                                    for ask_data in data.get('asks', []):
                                        price, size_str, _ = ask_data
                                        size = float(size_str)
                                        if size > 0:
                                            current_asks[price] = size
                                        else:
                                            current_asks.pop(price, None)
                                    
                                    for bid_data in data.get('bids', []):
                                        price, size_str, _ = bid_data
                                        size = float(size_str)
                                        if size > 0:
                                            current_bids[price] = size
                                        else:
                                            current_bids.pop(price, None)
                                
                                # 提取最优买卖价并写入
                                if current_asks and current_bids:
                                    try:
                                        # 用float()转换后比较，但保留原始字符串
                                        best_ask_price = min(current_asks.keys(), key=float)
                                        best_ask_size = current_asks[best_ask_price]
                                        
                                        best_bid_price = max(current_bids.keys(), key=float)
                                        best_bid_size = current_bids[best_bid_price]
                                        
                                        # 计算mid和spread
                                        best_ask_float = float(best_ask_price)
                                        best_bid_float = float(best_bid_price)
                                        mid = (best_ask_float + best_bid_float) / 2
                                        spread = best_ask_float - best_bid_float
                                        
                                        row = {
                                            'ts': ts,
                                            'best_bid': best_bid_price,
                                            'best_bid_size': best_bid_size,
                                            'best_ask': best_ask_price,
                                            'best_ask_size': best_ask_size,
                                            'mid': round(mid, 8),
                                            'spread': round(spread, 8),
                                        }
                                        writer.writerow(row)
                                        output_count += 1
                                        
                                        # 每10万行打印一次进度
                                        if output_count % 100000 == 0:
                                            print(f"  已处理 {output_count:,} 行...")
                                    
                                    except Exception as e:
                                        if line_count <= 5:
                                            print(f"  警告: 提取价格时出错 (第 {line_count} 行): {e}")
                            
                            except json.JSONDecodeError:
                                if line_count <= 5:
                                    print(f"  警告: 第 {line_count} 行JSON解析错误")
                                continue
                            except Exception as e:
                                if line_count <= 5:
                                    print(f"  警告: 第 {line_count} 行处理错误: {e}")
                                continue
                    
                    print(f"  ✓ 完成: 输入 {line_count:,} 行 → 输出 {output_count:,} 行")
                    print(f"  保存到: {output_file}")
                    break  # 只处理第一个成员
        
        except Exception as e:
            print(f"  ✗ 错误: {e}")


def main():
    source_root = Path(r"D:\imperial_homework\third_year\other\q\okx ob btc 2026-01")
    output_root = Path(r"D:\imperial_homework\third_year\other\q\okx ob btc 2026-01 processed")
    
    processor = OrderbookProcessor(output_root)
    processor.process_all_files(source_root)
    
    print(f"\n✓ 所有文件处理完成！输出目录: {output_root}")


if __name__ == "__main__":
    main()
