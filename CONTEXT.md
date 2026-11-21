# Patente Pronta

A study tool for the Italian driving licence (patente A/B) theory exam, built on the official
bank of true/false questions.

## Question bank

**Chapter**:
A top-level division of the question bank, one of the 25 topics of the ministry's exam
programme (e.g. Segnali di divieto). It has a short title of our own and the PDF's full title.
_Avoid_: Category, area, subchapter

**Topic**:
A group of Questions about one subject, usually one road sign, inside a Chapter. Called
"quesito" in the source data and shown as "Quesito n" in the app; its id is the official
quesito number.
_Avoid_: Block, argument

**Question**:
A single true/false statement. Its Answer is either true or false. Its id is the official
question number.
_Avoid_: Statement, item

**Figure**:
An image (sign, intersection, warning light) shown with a Question. A Question can have
several; a Topic's Figures are those shared by all its Questions.

**Level**:
How hard a Question is for this learner: Easy, Medium or Hard. Every Question starts at its
Default Level and the learner can change it.
_Avoid_: Difficulty, simple/mid/tricky

**Default Level**:
The Level a Question had before the learner changed it.

**Seen Question**:
A Question the learner has answered or Revealed at least once, in any Attempt, even an
Interrupted Practice. The learner can also mark a Question as seen or not seen by hand in the
question list. An Exam or a Practice can be limited to Questions not seen yet.
_Avoid_: Done, studied

## Quizzes

**Exam**:
A timed simulation of the real test: 30 random Questions from different Topics, 20 minutes.
Passed with at least 27 correct; unanswered Questions count as wrong.
_Avoid_: Real quiz, test

**Practice**:
An untimed quiz showing each Question's Level, where the learner either answers a Question
or Reveals it.
_Avoid_: Practice exam, training

**Instant Feedback**:
A Practice option, on by default: the Answer is shown as soon as the learner answers or
Reveals a Question. Without it the Practice works like an Exam without a timer: answers can be
changed until the learner hands it in, and are checked only in the summary.

**Reveal**:
Showing a Question's Answer in a Practice instead of answering it. A Revealed Question
counts as done but not correct.
_Avoid_: Peek, check answer

**Wrong Question**:
A Question whose most recent answer, in any Attempt, was wrong or a Reveal. Answering it
correctly later makes it no longer wrong. A Practice can be limited to Wrong Questions; that
replaces the limit to Questions not seen yet, since every Wrong Question has been seen.

**Unlimited Practice**:
A Practice with no fixed number of Questions and always with Instant Feedback. It draws from
the Questions matching its filters in random order and reshuffles once they have all been
asked. Showing each Question's Level is optional. The learner ends it whenever they like.
_Avoid_: Infinite mode, endless quiz

**Re-ask**:
A Question asked again in an Unlimited Practice because it was answered wrong or Revealed. It
comes back three times at growing gaps (about 5, then 10, then 20 Questions apart); a wrong
answer to a Re-ask starts the series over.
_Avoid_: Retry, repeat

**Streak**:
A run of consecutive correct answers in an Unlimited Practice. Its live stats show the best
Streak, the current one, the overall share of correct answers and the score over the last 30
answers.

**Level Filter**:
The set of Levels a quiz draws its Questions from, chosen before it starts.

**Chapter Filter**:
The set of Chapters a Practice or an Unlimited Practice draws its Questions from.

**Attempt**:
One Exam, Practice or Unlimited Practice the learner started, with their answer to each
Question.
_Avoid_: Session, run

**Completed Attempt**:
A submitted Exam, a Practice in which every Question was answered or Revealed, or an
Unlimited Practice the learner ended after answering at least one Question (the Question left
open is dropped; one ended with no answers is discarded). Only Completed Attempts appear in
the history and the progress chart.

**Interrupted Practice**:
A Practice the learner ended before every Question was done. It is kept out of the history.
