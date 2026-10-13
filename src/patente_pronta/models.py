from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel
from pydantic import Field as PydanticField
from sqlalchemy import JSON, Column
from sqlmodel import Field, Relationship, SQLModel


class Level(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class Mode(StrEnum):
    EXAM = "exam"
    PRACTICE = "practice"


class Chapter(SQLModel, table=True):
    id: int = Field(primary_key=True)
    title: str
    full_title: str
    topics: list["Topic"] = Relationship(
        back_populates="chapter", sa_relationship_kwargs={"order_by": "Topic.id"}
    )


class Topic(SQLModel, table=True):
    id: int = Field(primary_key=True)
    chapter_id: int = Field(foreign_key="chapter.id", index=True)
    figures: list[str] = Field(sa_column=Column(JSON, nullable=False))
    chapter: Chapter = Relationship(back_populates="topics")
    questions: list["Question"] = Relationship(
        back_populates="topic", sa_relationship_kwargs={"order_by": "Question.position"}
    )


class Question(SQLModel, table=True):
    id: int = Field(primary_key=True)
    topic_id: int = Field(foreign_key="topic.id", index=True)
    position: int
    text: str
    answer: bool
    figures: list[str] = Field(sa_column=Column(JSON, nullable=False))
    level: Level = Field(index=True)
    default_level: Level
    seen: bool
    topic: Topic = Relationship(back_populates="questions")


class Attempt(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    mode: Mode
    levels: str
    instant_feedback: bool
    started_at: datetime
    deadline: datetime | None
    finished_at: datetime | None
    correct: int | None
    answers: list["AttemptAnswer"] = Relationship(
        back_populates="attempt", sa_relationship_kwargs={"order_by": "AttemptAnswer.position"}
    )

    @property
    def is_complete(self) -> bool:
        if self.finished_at is None:
            return False
        return self.mode == Mode.EXAM or all(answer.is_done for answer in self.answers)

    @property
    def level_counts(self) -> dict[Level, int]:
        counts = dict.fromkeys(Level, 0)
        for answer in self.answers:
            if answer.level is not None:
                counts[answer.level] += 1
        return counts


class AttemptAnswer(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    attempt_id: int = Field(foreign_key="attempt.id", index=True)
    position: int
    question_id: int = Field(foreign_key="question.id")
    given: bool | None
    revealed: bool
    level: Level | None
    attempt: Attempt = Relationship(back_populates="answers")
    question: Question = Relationship()

    @property
    def is_done(self) -> bool:
        return self.given is not None or self.revealed

    @property
    def is_correct(self) -> bool:
        return not self.revealed and self.given == self.question.answer


class ExamSettings(BaseModel):
    levels: list[Level]
    unseen_only: bool


class PracticeSettings(BaseModel):
    levels: list[Level]
    chapters: list[int] | None
    count: int = PydanticField(ge=1, le=1000)
    unseen_only: bool
    instant_feedback: bool


class RevealIn(BaseModel):
    position: int


class AnswerIn(BaseModel):
    position: int
    given: bool


class LevelIn(BaseModel):
    level: Level


class LevelOut(BaseModel):
    level: Level
    default_level: Level
