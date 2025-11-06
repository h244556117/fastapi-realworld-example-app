-- name: get-articles-with-details
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
         LEFT JOIN favorites rf ON a.id = rf.article_id AND rf.user_id = (SELECT id FROM users WHERE username = :requested_username)::uuid
         LEFT JOIN articles_to_tags att ON a.id = att.article_id
         LEFT JOIN tags t ON att.tag = t.tag
WHERE (:tag IS NULL OR t.tag = :tag)
  AND (:author IS NULL OR u.username = :author)
  AND (:favorited IS NULL OR a.id IN (SELECT article_id FROM favorites WHERE user_id = (SELECT id FROM users WHERE username = :favorited)))
GROUP BY a.id, u.id, f.favorites_count, rf.user_id
ORDER BY a.created_at DESC
LIMIT :limit
OFFSET :offset;

-- name: get-article-by-slug-with-details
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
         LEFT JOIN favorites rf ON a.id = rf.article_id AND rf.user_id = (SELECT id FROM users WHERE username = :requested_username)::uuid
         LEFT JOIN articles_to_tags att ON a.id = att.article_id
         LEFT JOIN tags t ON att.tag = t.tag
WHERE a.slug = :slug
GROUP BY a.id, u.id, f.favorites_count, rf.user_id
LIMIT 1;
