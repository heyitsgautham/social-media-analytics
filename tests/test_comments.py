# tests/test_comments.py
"""Tests for comment analysis service."""

import pytest
from unittest.mock import MagicMock
from datetime import datetime, timedelta

from app.services.comments import (
    CommentAnalyzer,
    analyze_comment_depth,
    detect_viral_comment_chains,
    get_comment_tree_structure,
    CommentDepthAnalysis,
    ViralChainAnalysis,
)
from app.models import Comment, Post, User


class MockComment:
    """Mock comment for testing without database."""
    
    def __init__(self, id: int, parent_id: int = None, upvotes: int = 0, post_id: int = 1, user_id: int = 1):
        self.id = id
        self.parent_id = parent_id
        self.upvotes = upvotes
        self.post_id = post_id
        self.user_id = user_id
        self.body = f"Comment {id} body"
        self.created_at = datetime.utcnow()


class MockPost:
    """Mock post for testing."""
    
    def __init__(self, id: int):
        self.id = id
        self.content = f"Post {id} content"
        self.created_at = datetime.utcnow()


class TestCommentAnalyzer:
    """Test the CommentAnalyzer class directly."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = CommentAnalyzer(viral_min_replies=2, viral_min_upvotes=5)
        self.mock_db = MagicMock()
    
    def test_empty_post_depth_analysis(self):
        """Test depth analysis with no comments."""
        # Mock database to return empty comment list
        self.mock_db.query().filter().all.return_value = []
        self.mock_db.query().filter().first.return_value = MockPost(1)
        
        result = self.analyzer.analyze_depth(self.mock_db, 1)
        
        assert result.post_id == 1
        assert result.max_depth == 0
        assert result.total_comments == 0
        assert result.total_replies == 0
        assert result.average_replies_per_comment == 0.0
    
    def test_single_level_comments_depth(self):
        """Test depth analysis with only top-level comments."""
        comments = [
            MockComment(1),  # top-level
            MockComment(2),  # top-level
            MockComment(3),  # top-level
        ]
        
        self.mock_db.query().filter().all.return_value = comments
        self.mock_db.query().filter().first.return_value = MockPost(1)
        
        result = self.analyzer.analyze_depth(self.mock_db, 1)
        
        assert result.post_id == 1
        assert result.max_depth == 1
        assert result.total_comments == 3
        assert result.total_replies == 0  # no replies since all are top-level
        assert result.average_replies_per_comment == 0.0
    
    def test_nested_comments_depth(self):
        """Test depth analysis with nested comments."""
        comments = [
            MockComment(1),            # depth 1
            MockComment(2, parent_id=1),  # depth 2
            MockComment(3, parent_id=2),  # depth 3
            MockComment(4, parent_id=2),  # depth 3
            MockComment(5),            # depth 1
            MockComment(6, parent_id=5),  # depth 2
        ]
        
        self.mock_db.query().filter().all.return_value = comments
        self.mock_db.query().filter().first.return_value = MockPost(1)
        
        result = self.analyzer.analyze_depth(self.mock_db, 1)
        
        assert result.post_id == 1
        assert result.max_depth == 3
        assert result.total_comments == 6
        assert result.total_replies == 4  # 4 comments have parents
        # avg replies: comment 1 has 1 reply, comment 2 has 2 replies, comment 5 has 1 reply, others have 0
        # total replies across all comments: 4, so 4/6 = 0.67
        expected_avg = 4 / 6
        assert abs(result.average_replies_per_comment - expected_avg) < 0.01
    
    def test_deep_linear_chain(self):
        """Test depth analysis with a deep linear chain."""
        comments = [
            MockComment(1),            # depth 1
            MockComment(2, parent_id=1),  # depth 2
            MockComment(3, parent_id=2),  # depth 3
            MockComment(4, parent_id=3),  # depth 4
            MockComment(5, parent_id=4),  # depth 5
        ]
        
        self.mock_db.query().filter().all.return_value = comments
        self.mock_db.query().filter().first.return_value = MockPost(1)
        
        result = self.analyzer.analyze_depth(self.mock_db, 1)
        
        assert result.post_id == 1
        assert result.max_depth == 5
        assert result.total_comments == 5
        assert result.total_replies == 4
    
    def test_post_not_found(self):
        """Test behavior when post doesn't exist."""
        self.mock_db.query().filter().first.return_value = None
        
        with pytest.raises(ValueError, match="Post 999 not found"):
            self.analyzer.analyze_depth(self.mock_db, 999)
    
    def test_viral_chain_no_comments(self):
        """Test viral chain detection with no comments."""
        self.mock_db.query().filter().all.return_value = []
        self.mock_db.query().filter().first.return_value = MockPost(1)
        
        result = self.analyzer.detect_viral_chains(self.mock_db, 1)
        
        assert result.post_id == 1
        assert result.longest_chain_length == 0
        assert result.longest_chain_comments == []
        assert result.total_viral_chains == 0
        assert result.viral_criteria_met is False
    
    def test_viral_chain_no_viral_comments(self):
        """Test viral chain detection when no comments meet viral criteria."""
        comments = [
            MockComment(1, upvotes=1),    # not viral (< 5 upvotes, < 2 replies)
            MockComment(2, parent_id=1, upvotes=2),  # not viral
            MockComment(3, upvotes=3),    # not viral
        ]
        
        self.mock_db.query().filter().all.return_value = comments
        self.mock_db.query().filter().first.return_value = MockPost(1)
        
        result = self.analyzer.detect_viral_chains(self.mock_db, 1)
        
        assert result.longest_chain_length == 0
        assert result.total_viral_chains == 0
        assert result.viral_criteria_met is False
    
    def test_viral_chain_single_viral_comment(self):
        """Test viral chain detection with a single viral comment."""
        comments = [
            MockComment(1, upvotes=10),   # viral due to upvotes
            MockComment(2, parent_id=1, upvotes=1),  # not viral
        ]
        
        self.mock_db.query().filter().all.return_value = comments
        self.mock_db.query().filter().first.return_value = MockPost(1)
        
        result = self.analyzer.detect_viral_chains(self.mock_db, 1)
        
        # Single viral comment doesn't form a chain (need ≥2 comments)
        assert result.longest_chain_length == 0
        assert result.total_viral_chains == 0
        assert result.viral_criteria_met is False
    
    def test_viral_chain_detection(self):
        """Test viral chain detection with a proper viral chain."""
        comments = [
            MockComment(1, upvotes=10),      # viral due to upvotes
            MockComment(2, parent_id=1, upvotes=8),  # viral due to upvotes  
            MockComment(3, parent_id=2, upvotes=6),  # viral due to upvotes
            MockComment(4, parent_id=2, upvotes=1),  # not viral (sibling of 3)
            MockComment(5, upvotes=1),       # not viral root
        ]
        
        self.mock_db.query().filter().all.return_value = comments
        self.mock_db.query().filter().first.return_value = MockPost(1)
        
        result = self.analyzer.detect_viral_chains(self.mock_db, 1)
        
        assert result.longest_chain_length == 3  # comments 1->2->3
        assert result.longest_chain_comments == [1, 2, 3]
        assert result.total_viral_chains >= 1
        assert result.viral_criteria_met is True
    
    def test_viral_chain_by_replies(self):
        """Test viral chain detection based on reply count."""
        comments = [
            MockComment(1, upvotes=1),       # viral due to 2 replies
            MockComment(2, parent_id=1, upvotes=1),  # viral due to 2 replies
            MockComment(3, parent_id=1, upvotes=1),  # makes comment 1 viral
            MockComment(4, parent_id=2, upvotes=1),  # viral due to 1 reply (but needs 2)
            MockComment(5, parent_id=2, upvotes=1),  # makes comment 2 viral
        ]
        
        self.mock_db.query().filter().all.return_value = comments
        self.mock_db.query().filter().first.return_value = MockPost(1)
        
        result = self.analyzer.detect_viral_chains(self.mock_db, 1)
        
        # Comment 1 has 2 replies (viral), comment 2 has 2 replies (viral)
        # So we should have a chain of at least 2 comments
        assert result.longest_chain_length >= 2
        assert result.viral_criteria_met is True
    
    def test_multiple_viral_chains(self):
        """Test detection of multiple independent viral chains."""
        comments = [
            # First chain
            MockComment(1, upvotes=10),      # viral
            MockComment(2, parent_id=1, upvotes=8),  # viral
            
            # Second chain  
            MockComment(3, upvotes=12),      # viral
            MockComment(4, parent_id=3, upvotes=7),  # viral
            MockComment(5, parent_id=4, upvotes=6),  # viral
            
            # Non-viral comment
            MockComment(6, upvotes=1),       # not viral
        ]
        
        self.mock_db.query().filter().all.return_value = comments
        self.mock_db.query().filter().first.return_value = MockPost(1)
        
        result = self.analyzer.detect_viral_chains(self.mock_db, 1)
        
        assert result.longest_chain_length == 3  # second chain is longer
        assert result.total_viral_chains >= 2
        assert result.viral_criteria_met is True
    
    def test_is_viral_comment(self):
        """Test viral comment detection logic."""
        # Test upvotes threshold
        viral_upvotes = MockComment(1, upvotes=5)  # meets upvotes threshold
        not_viral_upvotes = MockComment(2, upvotes=4)  # below threshold
        
        # Mock children cache for reply testing
        self.analyzer._children_cache = {
            3: [MockComment(4), MockComment(5)],  # 2 replies (meets threshold)
            6: [MockComment(7)],  # 1 reply (below threshold)
            8: [],  # no replies
        }
        
        viral_replies = MockComment(3, upvotes=0)  # meets replies threshold
        not_viral_replies = MockComment(6, upvotes=0)  # below threshold
        not_viral_none = MockComment(8, upvotes=0)  # no replies
        
        assert self.analyzer._is_viral_comment(viral_upvotes) is True
        assert self.analyzer._is_viral_comment(not_viral_upvotes) is False
        assert self.analyzer._is_viral_comment(viral_replies) is True
        assert self.analyzer._is_viral_comment(not_viral_replies) is False
        assert self.analyzer._is_viral_comment(not_viral_none) is False


class TestServiceFunctions:
    """Test the top-level service functions."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_db = MagicMock()
    
    def test_analyze_comment_depth_function(self):
        """Test the analyze_comment_depth convenience function."""
        comments = [MockComment(1), MockComment(2, parent_id=1)]
        self.mock_db.query().filter().all.return_value = comments
        self.mock_db.query().filter().first.return_value = MockPost(1)
        
        result = analyze_comment_depth(self.mock_db, 1)
        
        assert isinstance(result, CommentDepthAnalysis)
        assert result.post_id == 1
        assert result.max_depth == 2
    
    def test_detect_viral_comment_chains_function(self):
        """Test the detect_viral_comment_chains convenience function."""
        comments = [MockComment(1, upvotes=10), MockComment(2, parent_id=1, upvotes=8)]
        self.mock_db.query().filter().all.return_value = comments
        self.mock_db.query().filter().first.return_value = MockPost(1)
        
        result = detect_viral_comment_chains(self.mock_db, 1)
        
        assert isinstance(result, ViralChainAnalysis)
        assert result.post_id == 1
    
    def test_get_comment_tree_structure_empty(self):
        """Test comment tree structure with no comments."""
        self.mock_db.query().filter().all.return_value = []
        self.mock_db.query().filter().first.return_value = MockPost(1)
        
        result = get_comment_tree_structure(self.mock_db, 1)
        
        assert result["post_id"] == 1
        assert result["comments"] == []
    
    def test_get_comment_tree_structure_nested(self):
        """Test comment tree structure with nested comments."""
        comments = [
            MockComment(1),
            MockComment(2, parent_id=1),
            MockComment(3, parent_id=1),
            MockComment(4, parent_id=2),
        ]
        
        self.mock_db.query().filter().all.return_value = comments
        self.mock_db.query().filter().first.return_value = MockPost(1)
        
        result = get_comment_tree_structure(self.mock_db, 1)
        
        assert result["post_id"] == 1
        assert len(result["comments"]) == 1  # one root comment
        
        root_comment = result["comments"][0]
        assert root_comment["id"] == 1
        assert len(root_comment["children"]) == 2  # comments 2 and 3
        
        # Check nested structure
        child_2 = next(c for c in root_comment["children"] if c["id"] == 2)
        assert len(child_2["children"]) == 1  # comment 4
        assert child_2["children"][0]["id"] == 4
        
        child_3 = next(c for c in root_comment["children"] if c["id"] == 3)
        assert len(child_3["children"]) == 0  # no children


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = CommentAnalyzer()
        self.mock_db = MagicMock()
    
    def test_circular_reference_protection(self):
        """Test that circular references don't cause infinite loops."""
        # This is more of a data integrity test - in practice, FK constraints prevent this
        # But we should handle it gracefully if it occurs
        comments = [
            MockComment(1, parent_id=2),  # points to comment 2
            MockComment(2, parent_id=1),  # points to comment 1 (circular!)
        ]
        
        self.mock_db.query().filter().all.return_value = comments
        self.mock_db.query().filter().first.return_value = MockPost(1)
        
        # This should complete without infinite loops
        # The algorithm naturally handles this since it builds the tree from parent->child relationships
        result = self.analyzer.analyze_depth(self.mock_db, 1)
        
        # Both comments will be treated as roots since they don't have valid parents in the filtered set
        assert result.total_comments == 2
    
    def test_large_depth_chain(self):
        """Test performance with deep comment chains."""
        # Create a chain of 100 comments
        comments = [MockComment(1)]  # root
        for i in range(2, 101):
            comments.append(MockComment(i, parent_id=i-1))
        
        self.mock_db.query().filter().all.return_value = comments
        self.mock_db.query().filter().first.return_value = MockPost(1)
        
        result = self.analyzer.analyze_depth(self.mock_db, 1)
        
        assert result.max_depth == 100
        assert result.total_comments == 100
        assert result.total_replies == 99
    
    def test_wide_tree_structure(self):
        """Test performance with wide comment trees."""
        # Create one root with 50 direct children
        comments = [MockComment(1)]  # root
        for i in range(2, 52):
            comments.append(MockComment(i, parent_id=1))
        
        self.mock_db.query().filter().all.return_value = comments
        self.mock_db.query().filter().first.return_value = MockPost(1)
        
        result = self.analyzer.analyze_depth(self.mock_db, 1)
        
        assert result.max_depth == 2
        assert result.total_comments == 51
        assert result.total_replies == 50
        assert result.average_replies_per_comment == 50 / 51  # root has 50 replies, others have 0


class TestCaching:
    """Test memoization functionality."""
    
    def test_cache_enabled_performance(self):
        """Test that caching improves performance for repeated subtree calculations."""
        analyzer_cached = CommentAnalyzer(cache_enabled=True)
        analyzer_no_cache = CommentAnalyzer(cache_enabled=False)
        
        # Create a balanced binary tree structure
        comments = []
        for i in range(1, 16):  # 15 nodes
            if i == 1:
                comments.append(MockComment(i))  # root
            else:
                parent_id = i // 2
                comments.append(MockComment(i, parent_id=parent_id))
        
        mock_db = MagicMock()
        mock_db.query().filter().all.return_value = comments
        mock_db.query().filter().first.return_value = MockPost(1)
        
        # Both should give same results
        result_cached = analyzer_cached.analyze_depth(mock_db, 1)
        result_no_cache = analyzer_no_cache.analyze_depth(mock_db, 1)
        
        assert result_cached.max_depth == result_no_cache.max_depth
        assert result_cached.total_comments == result_no_cache.total_comments
        
        # Check that cache was used
        assert len(analyzer_cached._depth_cache) > 0
        assert len(analyzer_no_cache._depth_cache) == 0


if __name__ == "__main__":
    pytest.main([__file__])