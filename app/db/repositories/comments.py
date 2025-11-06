from typing import List, Optional

from asyncpg import Connection, Record

from app.db.errors import EntityDoesNotExist
from app.db.queries.queries import queries
from app.db.repositories.base import BaseRepository
from app.models.domain.articles import Article
from app.models.domain.comments import Comment
from app.models.domain.profiles import Profile
from app.models.domain.users import User


class CommentsRepository(BaseRepository):
    def __init__(self, conn: Connection) -> None:
        super().__init__(conn)

    async def get_comment_by_id(
        self,
        *, 
        comment_id: int,
        article: Article,
        user: Optional[User] = None,
    ) -> Comment:
        # 使用优化查询获取评论及其作者信息
        comment_row = await self.connection.fetchrow(
            """
            SELECT c.id,
                   c.body,
                   c.created_at,
                   c.updated_at,
                   u.username AS author_username,
                   u.bio AS author_bio,
                   u.image AS author_image,
                   CASE WHEN ftf.follower_id IS NOT NULL THEN TRUE ELSE FALSE END AS is_following
            FROM commentaries c
                     JOIN users u ON c.author_id = u.id
                     JOIN articles a ON c.article_id = a.id AND a.slug = $2
                     LEFT JOIN followers_to_followings ftf ON u.id = ftf.following_id AND ftf.follower_id = (
                         SELECT id FROM users WHERE username = $3
                     )
            WHERE c.id = $1
            LIMIT 1;
            """,
            comment_id,
            article.slug,
            user.username if user else None
        )
        
        if not comment_row:
            raise EntityDoesNotExist(
                f"comment with id {comment_id} does not exist",
            )
        
        # 创建评论作者的profile
        author_profile = Profile(
            username=comment_row["author_username"],
            bio=comment_row["author_bio"],
            image=comment_row["author_image"],
            following=comment_row["is_following"] or False
        )
        
        # 创建并返回评论对象
        return Comment(
            id_=comment_row["id"],
            body=comment_row["body"],
            author=author_profile,
            created_at=comment_row["created_at"],
            updated_at=comment_row["updated_at"],
        )

    async def get_comments_for_article(
        self,
        *, 
        article: Article,
        user: Optional[User] = None,
    ) -> List[Comment]:
        # 使用优化查询一次性获取所有评论及其作者信息
        comments_rows = await self.connection.fetch(
            """
            SELECT c.id,
                   c.body,
                   c.created_at,
                   c.updated_at,
                   u.username AS author_username,
                   u.bio AS author_bio,
                   u.image AS author_image,
                   CASE WHEN ftf.follower_id IS NOT NULL THEN TRUE ELSE FALSE END AS is_following
            FROM commentaries c
                     JOIN users u ON c.author_id = u.id
                     JOIN articles a ON c.article_id = a.id AND a.slug = $1
                     LEFT JOIN followers_to_followings ftf ON u.id = ftf.following_id AND ftf.follower_id = (
                         SELECT id FROM users WHERE username = $2
                     )
            ORDER BY c.created_at DESC;
            """,
            article.slug,
            user.username if user else None
        )
        
        # 将查询结果转换为Comment对象列表
        comments = []
        for row in comments_rows:
            # 创建评论作者的profile
            author_profile = Profile(
                username=row["author_username"],
                bio=row["author_bio"],
                image=row["author_image"],
                following=row["is_following"] or False
            )
            
            # 创建评论对象
            comment = Comment(
                id_=row["id"],
                body=row["body"],
                author=author_profile,
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            comments.append(comment)
        
        return comments

    async def create_comment_for_article(
        self,
        *, 
        body: str,
        article: Article,
        user: User,
    ) -> Comment:
        # 创建新评论
        comment_row = await queries.create_new_comment(
            self.connection,
            body=body,
            article_slug=article.slug,
            author_username=user.username,
        )
        
        # 直接构造作者profile，无需额外查询
        author_profile = Profile(
            username=user.username,
            bio=user.bio,
            image=user.image,
            following=True  # 当前用户自己的评论，默认关注自己
        )
        
        # 创建并返回评论对象
        return Comment(
            id_=comment_row["id"],
            body=comment_row["body"],
            author=author_profile,
            created_at=comment_row["created_at"],
            updated_at=comment_row["updated_at"],
        )

    async def delete_comment(self, *, comment: Comment) -> None:
        await queries.delete_comment_by_id(
            self.connection,
            comment_id=comment.id_,
            author_username=comment.author.username,
        )
