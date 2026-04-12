import requests
import time
import json

def fetch_dmm_ending_soon_ids():
    url = "https://api.tv.dmm.co.jp/graphql"
    
    # 极简 Headers，只保留绕过年龄认证的 Cookie 和必要的请求头
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

    # GraphQL 原始查询语句
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
        node { id __typename }
        __typename
      }
      pageInfo {
        endCursor
        hasNextPage
        __typename
      }
      total
      __typename
    }
    __typename
  }
}"""

    has_next_page = True
    after_cursor = None
    all_video_ids = []
    page_count = 1

    print(">>> 阶段 1: 开始抓取 DMM TV 即将下架影片 ID (直连模式) ...")

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
            # 移除 proxies 参数，直接请求
            response = requests.post(url, headers=headers, json=payload, timeout=20)
            response.raise_for_status() 
            
            data = response.json()
            search_data = data.get("data", {}).get("fanzaTvPlus", {}).get("search", {})
            edges = search_data.get("edges", [])
            
            for edge in edges:
                video_id = edge.get("node", {}).get("id")
                if video_id:
                    all_video_ids.append(video_id)
                    
            page_info = search_data.get("pageInfo", {})
            has_next_page = page_info.get("hasNextPage", False)
            after_cursor = page_info.get("endCursor")
            
            total_items = search_data.get("total", "Unknown")
            print(f"[Page {page_count}] 成功抓取本页 {len(edges)} 条数据，累计: {len(all_video_ids)} / {total_items}")
            
            page_count += 1
            if has_next_page:
                time.sleep(1) # 依然保留延时，防止被服务器风控
                
        except requests.exceptions.HTTPError as e:
            print(f"HTTP 错误: {e}")
            if response.status_code in [403, 401]:
                print(">>> 严重错误: DMM API 拒绝了请求 (403/401)。GitHub 的美国 IP 可能已被封禁，或者极简 Cookie 失效。")
            break
        except Exception as e:
            print(f"抓取发生异常: {e}")
            break

    print(f"\n>>> DMM TV 数据抓取完毕，共获取到 {len(all_video_ids)} 个原始影片 ID。")

    # 如果抓取失败（比如 0 个 ID），直接退出，避免覆盖原有文件
    if not all_video_ids:
         print(">>> 未获取到任何 ID，程序退出。")
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
        print(f"获取 PREMIUM.txt 失败，不过滤: {e}")

    # 执行过滤
    if premium_ids_set:
        exclusive_video_ids = [vid for vid in all_video_ids if vid not in premium_ids_set]
    else:
        exclusive_video_ids = all_video_ids
        
    print(f"过滤掉了 {len(all_video_ids) - len(exclusive_video_ids)} 个重复 ID，剩下独有 ID: {len(exclusive_video_ids)} 个。")

    # ------------------ 阶段 3: 写入文件 ------------------ #
    print("\n>>> 阶段 3: 写入文件 ...")
    
    try:
        with open("dmm_ending_soon_ids_all.txt", "w", encoding="utf-8") as f_all:
            f_all.write("\n".join(all_video_ids) + "\n")
        
        with open("dmm_ending_soon_ids_exclusive.txt", "w", encoding="utf-8") as f_exc:
            f_exc.write("\n".join(exclusive_video_ids) + "\n")
                
        print(">>> 文件保存成功！")
        
    except Exception as e:
        print(f"文件保存失败: {e}")

if __name__ == "__main__":
    fetch_dmm_ending_soon_ids()