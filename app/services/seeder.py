from __future__ import annotations
import random
from datetime import datetime, timedelta
from typing import Sequence
from faker import Faker
from sqlalchemy.orm import Session

from app.models import (
    User, Post, Hashtag, PostHashtag, Comment, Engagement,
    EngagementKind, TargetType
)

fake = Faker()

def make_users(db: Session, n_users: int) -> list[User]:
    users = [User(handle=fake.unique.user_name()) for _ in range(n_users)]
    db.add_all(users); db.flush()
    return users

def make_hashtags(db: Session, n_tags: int) -> list[Hashtag]:
    # deterministic pool with some obvious domains
    base = [
        "ai","ml","datascience","python","fastapi","django","cloud","devops","startup","news",
        "music","sports","gaming","travel","food","fitness","health","finance","crypto","stocks"
    ]
    while len(base) < n_tags:
        base.append(fake.unique.word().lower())
    tags = [Hashtag(name=t) for t in base[:n_tags]]
    db.add_all(tags); db.flush()
    return tags

def make_posts(db: Session, users: Sequence[User], hashtags: Sequence[Hashtag], n_posts: int) -> list[Post]:
    posts: list[Post] = []
    for _ in range(n_posts):
        u = random.choice(users)
        created = fake.date_time_between(start_date="-60d", end_date="now")
        content = fake.sentence(nb_words=random.randint(8, 20))
        p = Post(user_id=u.id, content=content, created_at=created)
        db.add(p); posts.append(p)
    db.flush()

    # attach 1–4 hashtags each, biased so popular tags appear more
    tag_ids = [t.id for t in hashtags]
    weights = [5 if t.name in ("ai","python","news","sports","travel") else 1 for t in hashtags]
    for p in posts:
        k = random.randint(1, 4)
        chosen = random.choices(tag_ids, weights=weights, k=k)
        chosen = list(dict.fromkeys(chosen))  # dedupe
        for tag_id in chosen:
            db.add(PostHashtag(post_id=p.id, hashtag_id=tag_id))
    db.flush()
    return posts

def make_comment_tree(db: Session, post: Post, users: Sequence[User],
                      max_roots=3, max_depth=4, max_children=3):
    """
    Generate a small random tree of comments for one post.
    """
    def make_node(parent_id: int | None, depth: int):
        if depth > max_depth: return
        # each node has 0..max_children children, decreasing with depth
        n_children = random.randint(0, max(0, max_children - depth + 1))
        for _ in range(n_children):
            u = random.choice(users)
            when = post.created_at + timedelta(minutes=random.randint(1, 10*depth+5))
            c = Comment(
                post_id=post.id, user_id=u.id, parent_id=parent_id,
                body=fake.sentence(), upvotes=random.randint(0, 25),
                created_at=when
            )
            db.add(c); db.flush()
            make_node(c.id, depth + 1)

    roots = random.randint(0, max_roots)
    for _ in range(roots):
        u = random.choice(users)
        c = Comment(
            post_id=post.id, user_id=u.id, parent_id=None,
            body=fake.sentence(), upvotes=random.randint(0, 50),
            created_at=post.created_at + timedelta(minutes=random.randint(1, 30)),
        )
        db.add(c); db.flush()
        make_node(c.id, 2)

def make_comments(db: Session, posts: Sequence[Post], users: Sequence[User], frac_with_threads=0.6):
    for p in posts:
        if random.random() < frac_with_threads:
            make_comment_tree(db, p, users)

def make_engagements(db: Session, posts: Sequence[Post], users: Sequence[User]):
    """
    Scatter engagements with ratios like like:comment:share:view ≈ 5:2:1:10
    """
    kinds = (
        [EngagementKind.like]*5
        + [EngagementKind.bookmark]*1
        + [EngagementKind.share]*1
        + [EngagementKind.view]*10
    )
    for p in posts:
        n = random.randint(5, 80)
        for _ in range(n):
            u = random.choice(users)
            kind = random.choice(kinds)
            when = p.created_at + timedelta(minutes=random.randint(0, 1000))
            db.add(Engagement(
                user_id=u.id, target_type=TargetType.post,
                target_id=p.id, kind=kind, created_at=when
            ))
    db.flush()
