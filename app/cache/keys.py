from typing import Optional


class CacheKeys:
    """缓存键管理类"""
    
    # 文章相关
    @staticmethod
    def article_detail(slug: str, username: Optional[str] = None) -> str:
        """文章详情缓存键"""
        if username:
            return f"article:detail:{slug}:user:{username}"
        return f"article:detail:{slug}"
    
    @staticmethod
    def articles_list(page: int = 1, limit: int = 20, 
                      tag: Optional[str] = None, 
                      author: Optional[str] = None, 
                      favorited: Optional[str] = None) -> str:
        """文章列表缓存键"""
        key_parts = ["articles:list"]
        
        if tag:
            key_parts.append(f"tag:{tag}")
        elif author:
            key_parts.append(f"author:{author}")
        elif favorited:
            key_parts.append(f"favorited:{favorited}")
        else:
            key_parts.append("all")
        
        key_parts.append(f"page:{page}")
        key_parts.append(f"limit:{limit}")
        
        return ":".join(key_parts)
    
    @staticmethod
    def articles_feed(username: str, page: int = 1, limit: int = 20) -> str:
        """关注文章流缓存键"""
        return f"articles:list:feed:{username}:page:{page}:limit:{limit}"
    
    # 用户相关
    @staticmethod
    def user_profile(username: str) -> str:
        """用户信息缓存键"""
        return f"user:profile:{username}"
    
    @staticmethod
    def user_follower_count(username: str) -> str:
        """用户粉丝数缓存键"""
        return f"user:profile:{username}:follower_count"
    
    @staticmethod
    def user_following_count(username: str) -> str:
        """用户关注数缓存键"""
        return f"user:profile:{username}:following_count"
    
    # 评论相关
    @staticmethod
    def comments_list(slug: str, page: int = 1, limit: int = 20) -> str:
        """评论列表缓存键"""
        return f"comments:article:{slug}:page:{page}:limit:{limit}"
    
    # 标签相关
    @staticmethod
    def tags_all() -> str:
        """所有标签缓存键"""
        return "tags:all"