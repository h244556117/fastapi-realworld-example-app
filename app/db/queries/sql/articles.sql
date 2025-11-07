-- name: add-article-to-favorites!
WITH article_info AS (
    SELECT id FROM articles WHERE slug = :slug
), user_info AS (
    SELECT id FROM users WHERE username = :username
), insert_favorite AS (
    INSERT INTO favorites (user_id, article_id)
    SELECT user_info.id, article_info.id
    FROM user_info, article_info
    ON CONFLICT DO NOTHING
    RETURNING 1
)
UPDATE articles
SET favorites_count = favorites_count + 1
FROM insert_favorite
WHERE articles.id = (SELECT id FROM article_info);


-- name: remove-article-from-favorites!
WITH article_info AS (
    SELECT id FROM articles WHERE slug = :slug
), user_info AS (
    SELECT id FROM users WHERE username = :username
), delete_favorite AS (
    DELETE FROM favorites
    WHERE user_id = user_info.id AND article_id = article_info.id
    FROM user_info, article_info
    RETURNING 1
)
UPDATE articles
SET favorites_count = favorites_count - 1
FROM delete_favorite
WHERE articles.id = (SELECT id FROM article_info);


-- name: is-article-in-favorites^
SELECT CASE WHEN count(user_id) > 0 THEN TRUE ELSE FALSE END AS favorited
FROM favorites
WHERE user_id = (SELECT id FROM users WHERE username = :username)
  AND article_id = (SELECT id FROM articles WHERE slug = :slug);


-- name: get-favorites-count-for-article^
SELECT count(*) as favorites_count
FROM favorites
WHERE article_id = (SELECT id FROM articles WHERE slug = :slug);


-- name: get-tags-for-article-by-slug
SELECT t.tag
FROM tags t
         INNER JOIN articles_to_tags att ON
        t.tag = att.tag
        AND
        att.article_id = (SELECT id FROM articles WHERE slug = :slug);


-- name: get-article-by-slug^
SELECT id,
       slug,
       title,
       description,
       body,
       created_at,
       updated_at,
       (SELECT username FROM users WHERE id = author_id) AS author_username
FROM articles
WHERE slug = :slug
LIMIT 1;

-- name: get-article-by-slug-with-details^
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
       a.favorites_count AS favorites_count,
       CASE WHEN rf.user_id IS NOT NULL THEN TRUE ELSE FALSE END AS favorited,
       ARRAY_AGG(t.tag) FILTER (WHERE t.tag IS NOT NULL) AS tags
FROM articles a
         JOIN users u ON a.author_id = u.id
         LEFT JOIN favorites rf ON a.id = rf.article_id AND rf.user_id = (SELECT id FROM users WHERE username = :requested_username)
         LEFT JOIN articles_to_tags att ON a.id = att.article_id
         LEFT JOIN tags t ON att.tag = t.tag
WHERE a.slug = :slug
GROUP BY a.id, u.id, rf.user_id
LIMIT 1;


-- name: create-new-article<!
WITH author_subquery AS (
    SELECT id, username
    FROM users
    WHERE username = :author_username
)
INSERT
INTO articles (slug, title, description, body, author_id)
VALUES (:slug, :title, :description, :body, (SELECT id FROM author_subquery))
RETURNING
    id,
    slug,
    title,
    description,
    body,
        (SELECT username FROM author_subquery) as author_username,
    created_at,
    updated_at;


-- name: add-tags-to-article*!
INSERT INTO articles_to_tags (article_id, tag)
VALUES ((SELECT id FROM articles WHERE slug = :slug),
        (SELECT tag FROM tags WHERE tag = :tag))
ON CONFLICT DO NOTHING;


-- name: update-article<!
UPDATE articles
SET slug        = :new_slug,
    title       = :new_title,
    body        = :new_body,
    description = :new_description
WHERE slug = :slug
  AND author_id = (SELECT id FROM users WHERE username = :author_username)
RETURNING updated_at;


-- name: delete-article!
DELETE
FROM articles
WHERE slug = :slug
  AND author_id = (SELECT id FROM users WHERE username = :author_username);


-- name: filter-articles
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
         LEFT JOIN favorites rf ON a.id = rf.article_id AND rf.user_id = (SELECT id FROM users WHERE username = :requested_username)
         LEFT JOIN articles_to_tags att ON a.id = att.article_id
         LEFT JOIN tags t ON att.tag = t.tag
WHERE (:tag IS NULL OR t.tag = :tag)
  AND (:author IS NULL OR u.username = :author)
  AND (:favorited IS NULL OR a.id IN (SELECT article_id FROM favorites WHERE user_id = (SELECT id FROM users WHERE username = :favorited)))
GROUP BY a.id, u.id, f.favorites_count, rf.user_id
ORDER BY a.created_at DESC
LIMIT :limit
OFFSET :offset;

-- name: get-articles-for-feed
SELECT a.id,
       a.slug,
       a.title,
       a.description,
       a.body,
       a.created_at,
       a.updated_at,
       u.username AS author_username
FROM articles a
INNER JOIN followers_to_followings f ON f.following_id = a.author_id
INNER JOIN users u ON u.id = a.author_id
INNER JOIN users follower ON follower.id = f.follower_id
WHERE follower.username = :follower_username
ORDER BY a.created_at
LIMIT :limit
OFFSET :offset;
