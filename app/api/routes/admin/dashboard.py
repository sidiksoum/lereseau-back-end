from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
import re
from collections import Counter

from app.api.dependencies.auth import get_db, require_role
from app.models.user import User
from app.models.forum import ForumTopic, ForumReply

router = APIRouter()

@router.get("/stats")
def get_dashboard_stats(db: Session = Depends(get_db), current_admin: User = Depends(require_role("ADMIN"))):
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)
    seven_days_ago = now - timedelta(days=7)

    # 1. KPIs
    # Active Users (MAU)
    mau = db.query(User).filter(User.lastActive >= thirty_days_ago).count()
    
    # Premium Revenue
    premium_users = db.query(User).filter(User.isPremium == True).all()
    revenue = 0
    for u in premium_users:
        try:
            if u.premiumAmount:
                # Assuming premiumAmount might be something like "5000" or "5000 FCFA"
                val = re.sub(r'[^\d.]', '', u.premiumAmount)
                if val:
                    revenue += float(val)
        except:
            pass
    
    # Engagement Rate: Active users / Total users
    total_users = db.query(User).count()
    engagement_rate = (mau / total_users * 100) if total_users > 0 else 0
    
    # Critical Alerts
    reported_users = db.query(User).filter(User.reportsCount > 0).count()
    reported_topics = db.query(ForumTopic).filter(ForumTopic.reportsCount > 0).count()
    reported_replies = db.query(ForumReply).filter(ForumReply.reportsCount > 0).count()
    critical_alerts = reported_users + reported_topics + reported_replies

    # 2. Weekly Data
    weekly_data = []
    days = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
    
    # Generate data for the last 7 days dynamically
    for i in range(6, -1, -1):
        target_date = now - timedelta(days=i)
        day_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        
        new_users = db.query(User).filter(User.createdAt >= day_start, User.createdAt < day_end).count()
        active_users = db.query(User).filter(User.lastActive >= day_start, User.lastActive < day_end).count()
        
        day_name = days[target_date.weekday()]
        weekly_data.append({
            "day": day_name,
            "newUsers": new_users,
            "activeUsers": active_users
        })

    # 3. Forum Trends (Top Tags)
    # Extract hashtags from recent topics
    recent_topics = db.query(ForumTopic).filter(ForumTopic.createdAt >= thirty_days_ago).all()
    all_tags = []
    for topic in recent_topics:
        tags_in_title = re.findall(r'#\w+', topic.title or "")
        tags_in_content = re.findall(r'#\w+', topic.content or "")
        all_tags.extend(tags_in_title + tags_in_content)
        
    tag_counts = Counter(all_tags)
    top_tags = [{"tag": tag, "count": str(count)} for tag, count in tag_counts.most_common(5)]
    
    # Fallback if no tags exist
    if not top_tags:
        top_tags = [
            {"tag": "#Bienvenue", "count": "1"},
            {"tag": "#Discussions", "count": "1"}
        ]

    return {
        "kpis": {
            "mau": f"{mau}",
            "revenue": f"{int(revenue)} FCFA" if revenue > 0 else "0 FCFA",
            "engagementRate": f"{engagement_rate:.1f}%",
            "criticalAlerts": str(critical_alerts)
        },
        "weeklyData": weekly_data,
        "forumTrends": top_tags
    }
