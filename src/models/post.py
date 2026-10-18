import logging
import json
import re

from sqlmodel import Field, select, SQLModel, col
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class Post(SQLModel, table=True):
    __tablename__ = "huquqplus_posts"

    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    post_author: int = Field(default=0, index=True)
    post_date: datetime = Field(default_factory=datetime.utcnow, index=True)
    post_date_gmt: datetime = Field(default_factory=datetime.utcnow)
    post_content: Optional[str] = None
    post_title: Optional[str] = None
    post_excerpt: Optional[str] = None
    post_status: str = Field(default="publish", index=True)
    comment_status: str = Field(default="open")
    ping_status: str = Field(default="open")
    post_password: Optional[str] = None
    post_name: Optional[str] = Field(default=None, index=True)
    to_ping: Optional[str] = None
    pinged: Optional[str] = None
    post_modified: datetime = Field(default_factory=datetime.utcnow)
    post_modified_gmt: datetime = Field(default_factory=datetime.utcnow)
    post_content_filtered: Optional[str] = None
    post_parent: int = Field(default=0, index=True)
    guid: Optional[str] = None
    menu_order: int = Field(default=0)
    post_type: str = Field(default="post", index=True)
    post_mime_type: Optional[str] = None
    comment_count: int = Field(default=0)

    @classmethod
    def retrieve_faqs(cls, post_id: int | list, session):
        posts = session.exec(select(cls).where(col(cls.id).in_(post_id if type(post_id) is list else [post_id]))).all()

        if len(posts) == 0:
            return

        content = "\n\n".join([post.post_content for post in posts])
        pattern = r'<!-- wp:acf/faq ({.*?}) /-->'

        matches = re.findall(pattern, content)
        faqs = []
        for match in matches:
            try:
                faq_data = json.loads(match)
                if 'data' not in faq_data:
                    continue
                faq_entries = faq_data['data']
                question = faq_entries.get("faq_0_title")
                answer_html = faq_entries.get("faq_0_text")

                faqs.append({
                    "q": question,
                    "a": answer_html.encode().decode('unicode_escape')
                })

            except Exception as e:
                logger.warning("Error decoding JSON: %s", e)
        return faqs
