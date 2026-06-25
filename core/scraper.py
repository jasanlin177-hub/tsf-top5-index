from .config import TARGET_FUNDS  # 預設 5 檔短名→統編（換股後由 config 覆寫）
from .universe_scraper import fetch_universe, _normalize_id


class SitcaScraper:
    """
    從公會抓官方淨值（無狀態，只負責抓）。

    日更改用「統編精準比對」：重用 universe_scraper.fetch_universe()
    取當日全市場母體（已 AA1/TWD 濾、已同統編去重→路博邁自動取 T累積），
    再依 config 提供的「短名→統編」挑出要追蹤的成分股。
    比舊版關鍵字比對穩健（關鍵字 "T" 會誤中 "TWD" 導致抓錯級別）。
    """

    def fetch_data(self, date_str, targets=None):
        """
        輸入：date_str "YYYYMMDD"；targets = {短名: 統編}（None 則用 config 預設 5 檔）
        輸出：Dict {'統一奔騰': 120.5, ...}；查無資料回 None。
        """
        if targets is None:
            targets = TARGET_FUNDS

        universe = fetch_universe(date_str)
        if universe is None or universe.empty:
            return None  # 假日或淨值未發布

        nav_by_id = universe.set_index("基金統編")["淨值"].to_dict()

        results = {}
        for name, fund_id in targets.items():
            fid = _normalize_id(fund_id)
            if fid in nav_by_id:
                results[name] = float(nav_by_id[fid])
        return results or None
