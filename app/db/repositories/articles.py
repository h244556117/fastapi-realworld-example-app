from typing import List, Optional, Sequence, Union

from asyncpg import Connection, Record
from pypika import Query

from app.db.errors import EntityDoesNotExist
from app.db.queries.queries import queries
from app.db.queries.tables import (
    Parameter,
    articles,
    articles_to_tags,
    favorites,
    tags as tags_table,
    users,
)
from app.db.repositories.base import BaseRepository
from app.db.repositories.profiles import ProfilesRepository
from app.db.repositories.tags import TagsRepository
from app.models.domain.articles import Article
from app.models.domain.profiles import Profile
from app.models.domain.users import User

AUTHOR_USERNAME_ALIAS = "author_username"
SLUG_ALIAS = "slug"

CAMEL_OR_SNAKE_CASE_TO_WORDS = r"^[a-z\d_\-]+|[A-Z\d_\-][^A-Z\d_\-]*"


class ArticlesRepository(BaseRepository):  # noqa: WPS214
    def __init__(self, conn: Connection) -> None:
        super().__init__(conn)
        self._profiles_repo = ProfilesRepository(conn)
        self._tags_repo = TagsRepository(conn)

    async def create_article(  # noqa: WPS211
        self,
        *, 
        slug: str,
        title: str,
        description: str,
        body: str,
        author: User,
        tags: Optional[Sequence[str]] = None,
    ) -> Article:
        async with self.connection.transaction():
            article_row = await queries.create_new_article(
                self.connection,
                slug=slug,
                title=title,
                description=description,
                body=body,
                author_username=author.username,
            )

            if tags:
                await self._tags_repo.create_tags_that_dont_exist(tags=tags)
                await self._link_article_with_tags(slug=slug, tags=tags)

        return await self._get_article_from_db_record(
            article_row=article_row,
            slug=slug,
            author_username=article_row[AUTHOR_USERNAME_ALIAS],
            requested_user=author,
        )

    async def update_article(  # noqa: WPS211
        self,
        *, 
        article: Article,
        slug: Optional[str] = None,
        title: Optional[str] = None,
        body: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Article:
        updated_article = article.copy(deep=True)
        updated_article.slug = slug or updated_article.slug
        updated_article.title = title or article.title
        updated_article.body = body or article.body
        updated_article.description = description or article.description

        async with self.connection.transaction():
            updated_article.updated_at = await queries.update_article(
                self.connection,
                slug=article.slug,
                author_username=article.author.username,
                new_slug=updated_article.slug,
                new_title=updated_article.title,
                new_body=updated_article.body,
                new_description=updated_article.description,
            )

        return updated_article

    async def delete_article(self, *, article: Article) -> None:
        async with self.connection.transaction():
            await queries.delete_article(
                self.connection,
                slug=article.slug,
                author_username=article.author.username,
            )

    async def filter_articles(  # noqa: WPS211
        self,
        *, 
        tag: Optional[str] = None,
        author: Optional[str] = None,
        favorited: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        requested_user: Optional[User] = None,
    ) -> List[Article]:
        # Get requested username or None
        requested_username = requested_user.username if requested_user else None
        
        # Execute optimized query
        articles_rows = await self.connection.fetch(
            """
            SELECT a.id,
                   a.slug,
                   a.title,
                   a.description,
                   a.body,
                   a.created_at,
                   a.updated_at,
                   u.username AS author_username,
                   u.bio AS author_bio,
                   u.image AS author_image,
                   COALESCE(f.favorites_count, 0) AS favorites_count,
                   CASE WHEN rf.user_id IS NOT NULL THEN TRUE ELSE FALSE END AS favorited,
                   ARRAY_AGG(t.tag) FILTER (WHERE t.tag IS NOT NULL) AS tags
            FROM articles a
                     JOIN users u ON a.author_id = u.id
                     LEFT JOIN (
                SELECT article_id, COUNT(*) AS favorites_count
                FROM favorites
                GROUP BY article_id
            ) f ON a.id = f.article_id
                     LEFT JOIN favorites rf ON a.id = rf.article_id AND rf.user_id = (SELECT id FROM users WHERE username = $5)
                     LEFT JOIN articles_to_tags att ON a.id = att.article_id
                     LEFT JOIN tags t ON att.tag = t.tag
            WHERE ($1 IS NULL OR t.tag = $1)
              AND ($2 IS NULL OR u.username = $2)
              AND ($3 IS NULL OR a.id IN (SELECT article_id FROM favorites WHERE user_id = (SELECT id FROM users WHERE username = $3)))
            GROUP BY a.id, u.id, f.favorites_count, rf.user_id
            ORDER BY a.created_at DESC
            LIMIT $4
            OFFSET $6;
            """,
            tag,
            author,
            favorited,
            limit,
            requested_username,
            offset
        )
        
        # Convert rows to Article objects
        articles_list = []
        for row in articles_rows:
            # Create author profile
            author_profile = Profile(
                username=row["author_username"],
                bio=row["author_bio"],
                image=row["author_image"],
                following=False  # Will be updated if requested_user is provided
            )
            
            # Check if requested user is following the author
            if requested_user:
                author_profile.following = await self._profiles_repo.is_user_following_for_another_user(
                    target_user=author_profile,
                    requested_user=requested_user
                )
            
            # Create article object
            article = Article(
                id_=row["id"],
                slug=row["slug"],
                title=row["title"],
                description=row["description"],
                body=row["body"],
                author=author_profile,
                tags=row["tags"] or [],
                favorites_count=row["favorites_count"],
                favorited=row["favorited"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            articles_list.append(article)
        
        return articles_list

    async def get_articles_for_user_feed(
        self,
        *, 
        user: User,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Article]:
        # Execute optimized query
        articles_rows = await self.connection.fetch(
            """
            SELECT a.id,
                   a.slug,
                   a.title,
                   a.description,
                   a.body,
                   a.created_at,
                   a.updated_at,
                   u.username AS author_username,
                   u.bio AS author_bio,
                   u.image AS author_image,
                   COALESCE(f.favorites_count, 0) AS favorites_count,
                   CASE WHEN rf.user_id IS NOT NULL THEN TRUE ELSE FALSE END AS favorited,
                   ARRAY_AGG(t.tag) FILTER (WHERE t.tag IS NOT NULL) AS tags
            FROM articles a
                     JOIN users u ON a.author_id = u.id
                     JOIN followers_to_followings ftf ON a.author_id = ftf.following_id AND ftf.follower_id = (SELECT id FROM users WHERE username = $1)
                     LEFT JOIN (
                SELECT article_id, COUNT(*) AS favorites_count
                FROM favorites
                GROUP BY article_id
            ) f ON a.id = f.article_id
                     LEFT JOIN favorites rf ON a.id = rf.article_id AND rf.user_id = (SELECT id FROM users WHERE username = $1)
                     LEFT JOIN articles_to_tags att ON a.id = att.article_id
                     LEFT JOIN tags t ON att.tag = t.tag
            GROUP BY a.id, u.id, f.favorites_count, rf.user_id
            ORDER BY a.created_at DESC
            LIMIT $2
            OFFSET $3;
            """,
            user.username,
            limit,
            offset
        )
        
        # Convert rows to Article objects
        articles_list = []
        for row in articles_rows:
            # Create author profile (user is following since it's in feed)
            author_profile = Profile(
                username=row["author_username"],
                bio=row["author_bio"],
                image=row["author_image"],
                following=True
            )
            
            # Create article object
            article = Article(
                id_=row["id"],
                slug=row["slug"],
                title=row["title"],
                description=row["description"],
                body=row["body"],
                author=author_profile,
                tags=row["tags"] or [],
                favorites_count=row["favorites_count"],
                favorited=row["favorited"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            articles_list.append(article)
        
        return articles_list

    async def get_article_by_slug(
        self,
        *, 
        slug: str,
        requested_user: Optional[User] = None,
    ) -> Article:
        # Get requested username or None
        requested_username = requested_user.username if requested_user else None
        
        # Execute optimized query
        article_row = await self.connection.fetchrow(
            """
            SELECT a.id,
                   a.slug,
                   a.title,
                   a.description,
                   a.body,
                   a.created_at,
                   a.updated_at,
                   u.username AS author_username,
                   u.bio AS author_bio,
                   u.image AS author_image,
                   COALESCE(f.favorites_count, 0) AS favorites_count,
                   CASE WHEN rf.user_id IS NOT NULL THEN TRUE ELSE FALSE END AS favorited,
                   ARRAY_AGG(t.tag) FILTER (WHERE t.tag IS NOT NULL) AS tags
            FROM articles a
                     JOIN users u ON a.author_id = u.id
                     LEFT JOIN (
                SELECT article_id, COUNT(*) AS favorites_count
                FROM favorites
                GROUP BY article_id
            ) f ON a.id = f.article_id
                     LEFT JOIN favorites rf ON a.id = rf.article_id AND rf.user_id = (SELECT id FROM users WHERE username = $2)
                     LEFT JOIN articles_to_tags att ON a.id = att.article_id
                     LEFT JOIN tags t ON att.tag = t.tag
            WHERE a.slug = $1
            GROUP BY a.id, u.id, f.favorites_count, rf.user_id
            LIMIT 1;
            """,
            slug,
            requested_username
        )
        
        if not article_row:
            raise EntityDoesNotExist(f"article with slug {slug} does not exist")
        
        # Create author profile
        author_profile = Profile(
            username=article_row["author_username"],
            bio=article_row["author_bio"],
            image=article_row["author_image"],
            following=False  # Will be updated if requested_user is provided
        )
        
        # Check if requested user is following the author
        if requested_user:
            author_profile.following = await self._profiles_repo.is_user_following_for_another_user(
                target_user=author_profile,
                requested_user=requested_user
            )
        
        # Create article object
        return Article(
            id_=article_row["id"],
            slug=article_row["slug"],
            title=article_row["title"],
            description=article_row["description"],
            body=article_row["body"],
            author=author_profile,
            tags=article_row["tags"] or [],
            favorites_count=article_row["favorites_count"],
            favorited=article_row["favorited"],
            created_at=article_row["created_at"],
            updated_at=article_row["updated_at"],
        )

    async def get_tags_for_article_by_slug(self, *, slug: str) -> List[str]:
        tag_rows = await queries.get_tags_for_article_by_slug(
            self.connection,
            slug=slug,
        )
        return [row["tag"] for row in tag_rows]

    async def get_favorites_count_for_article_by_slug(self, *, slug: str) -> int:
        return (
            await queries.get_favorites_count_for_article(self.connection, slug=slug)
        )["favorites_count"]

    async def is_article_favorited_by_user(self, *, slug: str, user: User) -> bool:
        return (
            await queries.is_article_in_favorites(
                self.connection,
                username=user.username,
                slug=slug,
            )
        )["favorited"]

    async def add_article_into_favorites(self, *, article: Article, user: User) -> None:
        await queries.add_article_to_favorites(
            self.connection,
            username=user.username,
            slug=article.slug,
        )

    async def remove_article_from_favorites(
        self,
        *, 
        article: Article,
        user: User,
    ) -> None:
        await queries.remove_article_from_favorites(
            self.connection,
            username=user.username,
            slug=article.slug,
        )

    async def _get_article_from_db_record(
        self,
        *, 
        article_row: Record,
        slug: str,
        author_username: str,
        requested_user: Optional[User],
    ) -> Article:
        return Article(
            id_=article_row["id"],
            slug=slug,
            title=article_row["title"],
            description=article_row["description"],
            body=article_row["body"],
            author=await self._profiles_repo.get_profile_by_username(
                username=author_username,
                requested_user=requested_user,
            ),
            tags=await self.get_tags_for_article_by_slug(slug=slug),
            favorites_count=await self.get_favorites_count_for_article_by_slug(
                slug=slug,
            ),
            favorited=await self.is_article_favorited_by_user(
                slug=slug,
                user=requested_user,
            )
            if requested_user
            else False,
            created_at=article_row["created_at"],
            updated_at=article_row["updated_at"],
        )

    async def _link_article_with_tags(self, *, slug: str, tags: Sequence[str]) -> None:
        await queries.add_tags_to_article(
            self.connection,
            [{SLUG_ALIAS: slug, "tag": tag} for tag in tags],
        )
