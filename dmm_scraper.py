import requests
import time
import json
import os
from datetime import datetime

def fetch_dmm_ending_soon_ids():
    url = "https://api.tv.dmm.co.jp/graphql"
    
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
            response = requests.post(url, headers=headers, json=payload, timeout=20)
            response.raise_for_status() 
            
            data = response.json()
            search_data = data.get("data", {}).get("fanzaTvPlus", {}).get("search", {})
            edges = search_data.get("edges", [])
            
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
                time.sleep(1)
                
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

    if premium_ids_set:
        exclusive_videos = [v for v in all_videos if v.get("id") not in premium_ids_set]
    else:
        exclusive_videos = all_videos
        
    print(f"过滤掉了 {len(all_videos) - len(exclusive_videos)} 个重复影片，剩下独有影片: {len(exclusive_videos)} 个。")

    # ------------------ 阶段 3: 写入 JSON / TXT / 专属 README ------------------ #
    print("\n>>> 阶段 3: 生成数据文件与更新 README.md ...")
    
    # 转换为东九区时间 (日本时间)
    update_time = datetime.utcnow()
    update_time_str = update_time.strftime("%Y-%m-%d %H:%M:%S (UTC)")
    
    try:
        with open("dmm_ending_soon_ids_all.txt", "w", encoding="utf-8") as f_all:
            f_all.write("\n".join([v["id"] for v in all_videos]) + "\n")
            
        with open("dmm_ending_soon_ids_exclusive.txt", "w", encoding="utf-8") as f_exc:
            f_exc.write("\n".join([v["id"] for v in exclusive_videos]) + "\n")
            
        with open("dmm_ending_soon_exclusive.json", "w", encoding="utf-8") as f_json:
            json.dump(exclusive_videos, f_json, ensure_ascii=False, indent=2)
            
        # ---------- 为仓库首页特别定制的 README ----------
        readme_content = f"""# 🚨 Fanza TV Plus 独家即将下架影片

> **最后更新**: `{update_time_str}`
> **独家影片**: `{len(exclusive_videos)}` 部 (已过滤 PREMIUM 内容)
> 💡 **提示**: 点击【影片标题】跳转至 DMM 播放页；点击【封面图】查看高清大图。

---

"""     
        # 将所有独占影片渲染到 README 中
        # 为了防止图片过多导致 Github 卡顿，使用 details 折叠标签分块，或者直接瀑布流
        for v in exclusive_videos:
            # 优先使用大图
            img_url = v.get("packageLargeImage") or v.get("packageImage", "")
            title = v.get("title", "未知标题").replace("\n", " ")
            vid = v.get("id", "")
            score = v.get("averageReviewPoint")
            score_str = f"{score}" if score else "暂无"
            end_date = v.get("endDeliveryAt", "")[:10]
            desc = v.get("description", "暂无描述...")
            if len(desc) > 150:
                desc = desc[:150] + "..." # 描述太长截断一下
            
            dmm_link = f"https://tv.dmm.co.jp/vod/detail/?title_id={vid}"
            
            # 使用 Markdown 的图文混排结构
            readme_content += f"### 🎬 [{title}]({dmm_link})\n\n"
            readme_content += f"**ID**: `{vid}` &nbsp;&nbsp;|&nbsp;&nbsp; ⭐ **评分**: `{score_str}` &nbsp;&nbsp;|&nbsp;&nbsp; ⏳ **下架日期**: `{end_date}`\n\n"
            # 点击图片打开原图链接
            readme_content += f"[<img src='{img_url}' width='800'>]({img_url})\n\n"
            readme_content += f"> {desc}\n\n"
            readme_content += "---\n\n"

        with open("README.md", "w", encoding="utf-8") as f_readme:
            f_readme.write(readme_content)
            
        print(">>> JSON、TXT 和 README.md 生成成功！工作流执行完毕。")
        
    except Exception as e:
        print(f"文件保存失败: {e}")

if __name__ == "__main__":
    fetch_dmm_ending_soon_ids()
