from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.clock import utc_now


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    handle: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    posts: Mapped[list["Post"]] = relationship(back_populates="user")


class Post(Base):
    __tablename__ = "posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    user: Mapped[User] = relationship(back_populates="posts")
    hashtags: Mapped[list["PostHashtag"]] = relationship(
        back_populates="post", cascade="all, delete-orphan"
    )
    comments: Mapped[list["Comment"]] = relationship(back_populates="post")


Index("idx_posts_created", Post.created_at.desc())
Index("idx_posts_user_created", Post.user_id, Post.created_at)


class Hashtag(Base):
    __tablename__ = "hashtags"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)


class PostHashtag(Base):
    __tablename__ = "post_hashtags"
    post_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True
    )
    hashtag_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("hashtags.id", ondelete="CASCADE"), primary_key=True
    )

    post: Mapped[Post] = relationship(back_populates="hashtags")
    hashtag: Mapped[Hashtag] = relationship()


Index("idx_posthashtags_tag_post", PostHashtag.hashtag_id, PostHashtag.post_id)
Index("idx_posthashtags_post", PostHashtag.post_id)


class Comment(Base):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    parent_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("comments.id", ondelete="CASCADE"), nullable=True, index=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    upvotes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    post: Mapped[Post] = relationship(back_populates="comments")
    parent: Mapped["Comment | None"] = relationship(
        remote_side="Comment.id", back_populates="children"
    )
    children: Mapped[list["Comment"]] = relationship(back_populates="parent")


Index("idx_comments_parent", Comment.parent_id)


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
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    target_type: Mapped[TargetType] = mapped_column(
        Enum(TargetType, name="target_type"), nullable=False
    )
    target_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    kind: Mapped[EngagementKind] = mapped_column(
        Enum(EngagementKind, name="engagement_kind"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


Index("idx_engagements_target", Engagement.target_type, Engagement.target_id, Engagement.created_at)
Index("idx_engagements_user", Engagement.user_id, Engagement.created_at)


class HashtagCooccurrence(Base):
    __tablename__ = "hashtag_cooccurrence"
    hashtag_a: Mapped[int] = mapped_column(
        Integer, ForeignKey("hashtags.id", ondelete="CASCADE"), primary_key=True
    )
    hashtag_b: Mapped[int] = mapped_column(
        Integer, ForeignKey("hashtags.id", ondelete="CASCADE"), primary_key=True
    )
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (CheckConstraint("hashtag_a < hashtag_b", name="ck_co_pair_order"),)
