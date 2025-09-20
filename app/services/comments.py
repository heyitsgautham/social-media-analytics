# app/services/comments.py
"""Comment analysis service for recursive traversal and viral chain detection."""

from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models import Comment, Post


@dataclass
class CommentDepthAnalysis:
    """Result of comment depth analysis."""
    post_id: int
    max_depth: int
    total_comments: int
    total_replies: int
    average_replies_per_comment: float
    comment_tree_structure: Optional[Dict] = None


@dataclass
class ViralChainAnalysis:
    """Result of viral chain detection."""
    post_id: int
    longest_chain_length: int
    longest_chain_comments: List[int]  # comment IDs in the chain
    total_viral_chains: int
    viral_criteria_met: bool


class CommentAnalyzer:
    """Service for analyzing comment structures and detecting viral patterns."""
    
    def __init__(
        self, 
        viral_min_replies: int = 3, 
        viral_min_upvotes: int = 10,
        cache_enabled: bool = True
    ):
        """
        Initialize comment analyzer.
        
        Args:
            viral_min_replies: Minimum replies for a comment to be considered viral
            viral_min_upvotes: Minimum upvotes for a comment to be considered viral
            cache_enabled: Whether to enable memoization for performance
        """
        self.viral_min_replies = viral_min_replies
        self.viral_min_upvotes = viral_min_upvotes
        self.cache_enabled = cache_enabled
        self._depth_cache: Dict[int, int] = {}
        self._children_cache: Dict[int, List[Comment]] = {}
    
    def analyze_depth(self, db: Session, post_id: int) -> CommentDepthAnalysis:
        """
        Analyze comment depth for a given post.
        
        Args:
            db: Database session
            post_id: ID of the post to analyze
            
        Returns:
            CommentDepthAnalysis with depth metrics
        """
        # Clear cache for fresh analysis
        self._depth_cache.clear()
        self._children_cache.clear()
        
        # Verify post exists
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            raise ValueError(f"Post {post_id} not found")
        
        # Get all comments for this post
        comments = db.query(Comment).filter(Comment.post_id == post_id).all()
        
        if not comments:
            return CommentDepthAnalysis(
                post_id=post_id,
                max_depth=0,
                total_comments=0,
                total_replies=0,
                average_replies_per_comment=0.0
            )
        
        # Build comment tree structure
        comment_dict = {c.id: c for c in comments}
        root_comments = [c for c in comments if c.parent_id is None]
        
        # Precompute children for each comment
        for comment in comments:
            children = [c for c in comments if c.parent_id == comment.id]
            self._children_cache[comment.id] = children
        
        # Calculate depth metrics
        max_depth = 0
        total_replies = len(comments) - len(root_comments)
        
        for root_comment in root_comments:
            depth = self._calculate_depth(root_comment, comment_dict)
            max_depth = max(max_depth, depth)
        
        # Calculate average replies per comment
        reply_counts = [len(self._children_cache.get(c.id, [])) for c in comments]
        avg_replies = sum(reply_counts) / len(comments) if comments else 0.0
        
        return CommentDepthAnalysis(
            post_id=post_id,
            max_depth=max_depth,
            total_comments=len(comments),
            total_replies=total_replies,
            average_replies_per_comment=avg_replies
        )
    
    def detect_viral_chains(self, db: Session, post_id: int) -> ViralChainAnalysis:
        """
        Detect viral comment chains using backtracking.
        
        Args:
            db: Database session
            post_id: ID of the post to analyze
            
        Returns:
            ViralChainAnalysis with viral chain information
        """
        # Verify post exists
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            raise ValueError(f"Post {post_id} not found")
        
        # Get all comments for this post
        comments = db.query(Comment).filter(Comment.post_id == post_id).all()
        
        if not comments:
            return ViralChainAnalysis(
                post_id=post_id,
                longest_chain_length=0,
                longest_chain_comments=[],
                total_viral_chains=0,
                viral_criteria_met=False
            )
        
        # Build comment tree structure
        comment_dict = {c.id: c for c in comments}
        root_comments = [c for c in comments if c.parent_id is None]
        
        # Precompute children for each comment
        self._children_cache.clear()
        for comment in comments:
            children = [c for c in comments if c.parent_id == comment.id]
            self._children_cache[comment.id] = children
        
        # Find all viral chains using backtracking
        all_chains = []
        longest_chain = []
        
        for root_comment in root_comments:
            if self._is_viral_comment(root_comment):
                chains = self._find_viral_chains(root_comment, comment_dict, [])
                all_chains.extend(chains)
                
                # Track longest chain
                for chain in chains:
                    if len(chain) > len(longest_chain):
                        longest_chain = chain
        
        return ViralChainAnalysis(
            post_id=post_id,
            longest_chain_length=len(longest_chain),
            longest_chain_comments=[c.id for c in longest_chain],
            total_viral_chains=len(all_chains),
            viral_criteria_met=len(longest_chain) > 0
        )
    
    def _calculate_depth(self, comment: Comment, comment_dict: Dict[int, Comment]) -> int:
        """
        Recursively calculate the maximum depth from a given comment.
        
        Args:
            comment: Starting comment
            comment_dict: Dictionary of all comments by ID
            
        Returns:
            Maximum depth from this comment
        """
        if self.cache_enabled and comment.id in self._depth_cache:
            return self._depth_cache[comment.id]
        
        children = self._children_cache.get(comment.id, [])
        
        if not children:
            depth = 1
        else:
            max_child_depth = max(
                self._calculate_depth(child, comment_dict) 
                for child in children
            )
            depth = 1 + max_child_depth
        
        if self.cache_enabled:
            self._depth_cache[comment.id] = depth
        
        return depth
    
    def _is_viral_comment(self, comment: Comment) -> bool:
        """
        Check if a comment meets viral criteria.
        
        Args:
            comment: Comment to check
            
        Returns:
            True if comment is viral, False otherwise
        """
        reply_count = len(self._children_cache.get(comment.id, []))
        return (reply_count >= self.viral_min_replies or 
                comment.upvotes >= self.viral_min_upvotes)
    
    def _find_viral_chains(
        self, 
        comment: Comment, 
        comment_dict: Dict[int, Comment], 
        current_chain: List[Comment]
    ) -> List[List[Comment]]:
        """
        Use backtracking to find all viral chains starting from a comment.
        
        Args:
            comment: Current comment in the chain
            comment_dict: Dictionary of all comments by ID
            current_chain: Current chain being built
            
        Returns:
            List of all viral chains found
        """
        # Add current comment to chain
        new_chain = current_chain + [comment]
        chains = []
        
        # Get children of current comment
        children = self._children_cache.get(comment.id, [])
        viral_children = [child for child in children if self._is_viral_comment(child)]
        
        if not viral_children:
            # End of chain - if it has at least 2 comments, it's a valid chain
            if len(new_chain) >= 2:
                chains.append(new_chain)
        else:
            # Continue chain with each viral child
            for child in viral_children:
                child_chains = self._find_viral_chains(child, comment_dict, new_chain)
                chains.extend(child_chains)
            
            # Also consider the current chain as complete if it has at least 2 comments
            if len(new_chain) >= 2:
                chains.append(new_chain)
        
        return chains


# Global analyzer instance with default settings
comment_analyzer = CommentAnalyzer()


def analyze_comment_depth(db: Session, post_id: int) -> CommentDepthAnalysis:
    """
    Convenience function to analyze comment depth for a post.
    
    Args:
        db: Database session
        post_id: ID of the post to analyze
        
    Returns:
        CommentDepthAnalysis result
    """
    return comment_analyzer.analyze_depth(db, post_id)


def detect_viral_comment_chains(db: Session, post_id: int) -> ViralChainAnalysis:
    """
    Convenience function to detect viral comment chains for a post.
    
    Args:
        db: Database session
        post_id: ID of the post to analyze
        
    Returns:
        ViralChainAnalysis result
    """
    return comment_analyzer.detect_viral_chains(db, post_id)


def get_comment_tree_structure(db: Session, post_id: int) -> Dict:
    """
    Get nested JSON structure of comment tree (stretch goal).
    
    Args:
        db: Database session
        post_id: ID of the post
        
    Returns:
        Nested dictionary representing comment tree
    """
    # Verify post exists
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise ValueError(f"Post {post_id} not found")
    
    # Get all comments for this post
    comments = db.query(Comment).filter(Comment.post_id == post_id).all()
    
    if not comments:
        return {"post_id": post_id, "comments": []}
    
    # Build comment tree
    comment_dict = {c.id: c for c in comments}
    root_comments = [c for c in comments if c.parent_id is None]
    
    def build_tree_node(comment: Comment) -> Dict:
        children = [c for c in comments if c.parent_id == comment.id]
        return {
            "id": comment.id,
            "body": comment.body,
            "upvotes": comment.upvotes,
            "created_at": comment.created_at.isoformat(),
            "user_id": comment.user_id,
            "children": [build_tree_node(child) for child in children]
        }
    
    return {
        "post_id": post_id,
        "comments": [build_tree_node(comment) for comment in root_comments]
    }