from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, Text, ForeignKey, Enum, UniqueConstraint, Index, CheckConstraint
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    handle = Column(String(64), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    posts = relationship("Post", back_populates="user")

class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="posts")
    hashtags = relationship("PostHashtag", back_populates="post", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="post")

Index("idx_posts_created", Post.created_at.desc())

class Hashtag(Base):
    __tablename__ = "hashtags"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)

class PostHashtag(Base):
    __tablename__ = "post_hashtags"
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True)
    hashtag_id = Column(Integer, ForeignKey("hashtags.id", ondelete="CASCADE"), primary_key=True)

    post = relationship("Post", back_populates="hashtags")
    hashtag = relationship("Hashtag")

Index("idx_posthashtags_tag_post", PostHashtag.hashtag_id, PostHashtag.post_id)
Index("idx_posthashtags_post", PostHashtag.post_id)

class Comment(Base):
    __tablename__ = "comments"
    id = Column(Integer, primary_key=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    parent_id = Column(Integer, ForeignKey("comments.id", ondelete="CASCADE"), nullable=True, index=True)
    body = Column(Text, nullable=False)
    upvotes = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    post = relationship("Post", back_populates="comments")
    parent = relationship("Comment", remote_side=[id], backref="children")

Index("idx_comments_parent", Comment.parent_id)

from enum import Enum as PyEnum
class TargetType(str, PyEnum):
    post = "post"
    comment = "comment"

class EngagementKind(str, PyEnum):
    like = "like"
    share = "share"
    view = "view"
    bookmark = "bookmark"

class Engagement(Base):
    __tablename__ = "engagements"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    target_type = Column(Enum(TargetType, name="target_type"), nullable=False)
    target_id = Column(Integer, nullable=False, index=True)
    kind = Column(Enum(EngagementKind, name="engagement_kind"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

Index("idx_engagements_target", Engagement.target_type, Engagement.target_id, Engagement.created_at)
Index("idx_engagements_user", Engagement.user_id, Engagement.created_at)

class HashtagCooccurrence(Base):
    __tablename__ = "hashtag_cooccurrence"
    hashtag_a = Column(Integer, ForeignKey("hashtags.id", ondelete="CASCADE"), primary_key=True)
    hashtag_b = Column(Integer, ForeignKey("hashtags.id", ondelete="CASCADE"), primary_key=True)
    count = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        CheckConstraint("hashtag_a < hashtag_b", name="ck_co_pair_order"),
    )
