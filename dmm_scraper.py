import requests
import time
import json
import os
from datetime import datetime

def fetch_dmm_ending_soon_ids():
    url = "https://api.tv.dmm.co.jp/graphql"
    
    # 极简 Headers：绕过年龄限制，伪装浏览器
    headers = {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9",
        "content-type": "application/json",
        "origin": "https://tv.dmm.co.jp",
        "referer": "https://tv.dmm.co.jp/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "x-dmm-device": "BROWSER",
        "cookie": "age_check_done=1"
    }

    # 修复 422 错误：恢复 DMM 标准的 GraphQL 查询格式，严格遵守参数定义
    graphql_query = """query FetchFanzaTvPlusSearch($device: Device!, $keyword: String, $castIds: [String!], $genreIds: [String!], $makerIds: [String!], $seriesIds: [String!], $labelIds: [String!], $ppvShop: FanzaPPVShop, $viewingPlan: FanzaTvViewingPlan, $isForeign: Boolean, $isChildNg: Boolean, $sort: FanzaSvodSortKey, $first: Int, $after: String) {
  fanzaTvPlus(device: $device) {
    search(
      keyword: $keyword
      castIds: $castIds
      genreIds: $genreIds
      makerIds: $makerIds
      seriesIds: $seriesIds
      labelIds: $labelIds
      ppvShop: $ppvShop
      viewingPlan: $viewingPlan
      isForeign: $isForeign
      isChildNg: $isChildNg
      sort: $sort
      first: $first
      after: $after
    ) {
      edges {
        cursor
        node {
          id
          title
          averageReviewPoint
          packageImage
          packageLargeImage
          description
          startDeliveryAt
          endDeliveryAt
        }
      }
      pageInfo {
        endCursor
        hasNextPage
      }
      total
    }
  }
}"""

    has_next_page = True
    after_cursor = None
    all_videos = []
    page_count = 1

    print(">>> 阶段 1: 开始抓取 DMM TV 即将下架影片详细信息 (直连模式) ...")

    while has_next_page:
        # 获取 ALL 计划的影片
        variables = {
            "sort": "DELIVERY_ENDING_SOON",
            "device": "BROWSER",
            "first": 48,
            "isForeign": False
        }
        
        if after_cursor:
            variables["after"] = after_cursor
            
        payload = {
            "operationName": "FetchFanzaTvPlusSearch",
            "variables": variables,
            "query": graphql_query
        }

        try:
            # 发送请求
            response = requests.post(url, headers=headers, json=payload, timeout=20)
            response.raise_for_status() 
            
            data = response.json()
            search_data = data.get("data", {}).get("fanzaTvPlus", {}).get("search", {})
            edges = search_data.get("edges", [])
            
            # 保存完整的影片字典信息
            for edge in edges:
                node = edge.get("node", {})
                if node.get("id"):
                    all_videos.append(node)
                    
            page_info = search_data.get("pageInfo", {})
            has_next_page = page_info.get("hasNextPage", False)
            after_cursor = page_info.get("endCursor")
            
            total_items = search_data.get("total", "Unknown")
            print(f"[Page {page_count}] 成功抓取本页 {len(edges)} 条数据，累计: {len(all_videos)} / {total_items}")
            
            page_count += 1
            if has_next_page:
                time.sleep(1) # 延时 1 秒防止被封 IP
                
        except requests.exceptions.HTTPError as e:
            print(f"HTTP 错误: {e}")
            if response.status_code == 422:
                print(f"响应详情: {response.text}")
            elif response.status_code in [403, 401]:
                print(">>> 严重错误: DMM API 拒绝了请求 (403/401)。GitHub 的美国 IP 可能已被封禁。")
            break
        except Exception as e:
            print(f"抓取发生异常: {e}")
            break

    if not all_videos:
         print(">>> 未获取到任何影片，程序退出。")
         return

    # ------------------ 阶段 2: 获取 PREMIUM.txt 进行对比过滤 ------------------ #
    print("\n>>> 阶段 2: 获取 PREMIUM.txt 进行对比过滤 ...")
    premium_url = "https://raw.githubusercontent.com/CPCOM/isMonthly/main/Fanza/PREMIUM.txt"
    premium_ids_set = set()
    
    try:
        premium_response = requests.get(premium_url, timeout=15)
        premium_response.raise_for_status()
        for line in premium_response.text.splitlines():
            line = line.strip()
            if line:
                premium_ids_set.add(line)
        print(f"成功从 Github 获取到 {len(premium_ids_set)} 个 PREMIUM 影片 ID。")
    except Exception as e:
        print(f"获取 PREMIUM.txt 失败，将跳过过滤步骤: {e}")

    # 执行过滤
    if premium_ids_set:
        exclusive_videos = [v for v in all_videos if v.get("id") not in premium_ids_set]
    else:
        exclusive_videos = all_videos
        
    print(f"过滤掉了 {len(all_videos) - len(exclusive_videos)} 个重复影片，剩下独有影片: {len(exclusive_videos)} 个。")

    # ------------------ 阶段 3: 写入 JSON / TXT / README ------------------ #
    print("\n>>> 阶段 3: 生成数据文件与更新 README.md ...")
    update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        # 1. 保存所有影片 ID 的 txt 文件（未过滤）
        with open("dmm_ending_soon_ids_all.txt", "w", encoding="utf-8") as f_all:
            f_all.write("\n".join([v["id"] for v in all_videos]) + "\n")
            
        # 2. 保存独占影片 ID 的 txt 文件（已过滤）
        with open("dmm_ending_soon_ids_exclusive.txt", "w", encoding="utf-8") as f_exc:
            f_exc.write("\n".join([v["id"] for v in exclusive_videos]) + "\n")
            
        # 3. 保存独占影片的完整信息为 JSON (供网页前端读取)
        with open("dmm_ending_soon_exclusive.json", "w", encoding="utf-8") as f_json:
            json.dump(exclusive_videos, f_json, ensure_ascii=False, indent=2)
            
        # 4. 自动生成包含图文的 README.md
        readme_content = f"""# 🚨 DMM TV (FANZA) 独家即将下架影片

> **最后更新时间**: {update_time}
> **独家下架影片数量**: {len(exclusive_videos)} 部 (已过滤 PREMIUM 内容)
> 
> 👉 **[点击这里访问大图卡片展示页](https://{os.getenv('GITHUB_REPOSITORY_OWNER', '你的用户名')}.github.io/{os.getenv('GITHUB_REPOSITORY', '你的仓库名').split('/')[-1] if os.getenv('GITHUB_REPOSITORY') else '你的仓库名'}/)**

## 影片列表速览 (前50部)

| 封面 | 详细信息 |
| :--- | :--- |
"""
        for v in exclusive_videos[:50]:
            img_url = v.get("packageImage", "")
            title = v.get("title", "").replace("|", "\|") # 防止标题里的竖线破坏 Markdown 表格
            vid = v.get("id", "")
            score = v.get("averageReviewPoint", "无")
            end_date = v.get("endDeliveryAt", "")[:10]
            
            readme_content += f"| <img src='{img_url}' width='200'> | **ID**: `{vid}`<br>**标题**: {title}<br>⭐ **评分**: {score}<br>⏳ **下架日期**: {end_date} |\n"
            
        if len(exclusive_videos) > 50:
            readme_content += f"\n*...等共 {len(exclusive_videos)} 部影片，请点击上方展示页链接查看完整列表。*\n"

        with open("README.md", "w", encoding="utf-8") as f_readme:
            f_readme.write(readme_content)
            
        print(">>> JSON、TXT 和 README.md 生成成功！工作流执行完毕。")
        
    except Exception as e:
        print(f"文件保存失败: {e}")

if __name__ == "__main__":
    fetch_dmm_ending_soon_ids()
