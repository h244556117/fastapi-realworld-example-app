class CacheMonitor:
    """缓存监控"""
    
    hits: int = 0  # 命中次数
    misses: int = 0  # 未命中次数
    
    @classmethod
    def record_hit(cls):
        """记录缓存命中"""
        cls.hits += 1
    
    @classmethod
    def record_miss(cls):
        """记录缓存未命中"""
        cls.misses += 1
    
    @classmethod
    def get_stats(cls) -> dict:
        """获取统计信息"""
        total = cls.hits + cls.misses
        hit_rate = cls.hits / total if total > 0 else 0
        return {
            "hits": cls.hits,
            "misses": cls.misses,
            "total": total,
            "hit_rate": f"{hit_rate:.2%}"
        }