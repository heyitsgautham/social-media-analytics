# app/routes/comments.py
"""FastAPI routes for comment analysis endpoints."""

from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.db import get_session
from app.services.comments import (
    analyze_comment_depth,
    detect_viral_comment_chains,
    get_comment_tree_structure,
    CommentDepthAnalysis,
    ViralChainAnalysis,
)

router = APIRouter(prefix="/comments", tags=["comments"])


@router.get("/depth/{post_id}", response_model=Dict)
def get_comment_depth_analysis(
    post_id: int = Path(..., description="ID of the post to analyze", ge=1),
) -> Dict:
    """
    Analyze comment depth for a given post.
    
    Returns metrics including:
    - max_depth: Maximum nesting level of comments
    - total_comments: Total number of comments
    - total_replies: Number of replies (comments with parents)
    - average_replies_per_comment: Average replies per comment
    """
    try:
        with get_session() as db:
            analysis = analyze_comment_depth(db, post_id)
            
            return {
                "post_id": analysis.post_id,
                "max_depth": analysis.max_depth,
                "total_comments": analysis.total_comments,
                "total_replies": analysis.total_replies,
                "average_replies_per_comment": round(analysis.average_replies_per_comment, 2),
            }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/viral/{post_id}", response_model=Dict)
def get_viral_chain_analysis(
    post_id: int = Path(..., description="ID of the post to analyze", ge=1),
) -> Dict:
    """
    Detect viral comment chains for a given post.
    
    A viral chain is a sequence of comments where each comment has:
    - ≥3 replies OR ≥10 upvotes
    
    Returns:
    - longest_chain_length: Length of the longest viral chain
    - longest_chain_comments: Comment IDs in the longest chain
    - total_viral_chains: Total number of viral chains found
    - viral_criteria_met: Whether any viral chains were found
    """
    try:
        with get_session() as db:
            analysis = detect_viral_comment_chains(db, post_id)
            
            return {
                "post_id": analysis.post_id,
                "longest_chain_length": analysis.longest_chain_length,
                "longest_chain_comments": analysis.longest_chain_comments,
                "total_viral_chains": analysis.total_viral_chains,
                "viral_criteria_met": analysis.viral_criteria_met,
                "criteria": {
                    "min_replies": 3,
                    "min_upvotes": 10
                }
            }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/tree/{post_id}", response_model=Dict)
def get_comment_tree(
    post_id: int = Path(..., description="ID of the post to get comment tree for", ge=1),
) -> Dict:
    """
    Get nested JSON structure of comment tree (stretch goal).
    
    Returns a hierarchical structure showing the complete comment tree
    with all nested replies.
    """
    try:
        with get_session() as db:
            tree = get_comment_tree_structure(db, post_id)
            return tree
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")