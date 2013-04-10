import praw
from sys import argv, exit
from pprint import pprint
import logging
from time import time as time

class CommentStealer:
	_NEW_SUBMISSION_LIMIT = 50
	_SECONDS_PER_DAY = 86400
	_NORMAL_DELAY = 2
	_COMMENT_DELAY = 30
	_LOG_FILENAME = 'botlog.log'
	_USER_AGENT = 'stealstopcomments by /u/StealsTopComments'

	def __init__(self, subreddit, username, pw):
		self.subreddit_name = subreddit
		self.username = username
		self.pw = pw

		self.last_request_time = 0
		self.total_submissions_seen = 0
		self.reposts_seen = 0
		self.already_visited = set()

		logging.basicConfig(filename=self._LOG_FILENAME)

	def block_for(self, wait_time):
		""" Loops for wait_time seconds. Used to ensure we don't break reddit API 
		    guidelines about sending too many requests. """
		while time() - self.last_request_time < wait_time:
			continue
		self.last_request_time = time()

	def monitor(self):
		""" Monitors new posts in the given subreddit, detects reposts of the same link, 
		    finds the top comment in all previous posts, and adds a comment whose body
		    is the body of aforementioned top comment. """

		# Log in
		try:
			reddit = praw.Reddit(user_agent=self._USER_AGENT)
			reddit.login(self.username, self.pw)
		except praw.errors.InvalidUserPass:
			error('***** ERROR: Invalid username or password *****')

		subreddit = reddit.get_subreddit(self.subreddit_name)

		# Continuously monitor the subreddit
		while True:
			self.block_for(self._NORMAL_DELAY)
			new_submissions = subreddit.get_new(limit=self._NEW_SUBMISSION_LIMIT)

			# Iterating over new submissions
			print 'Checking batch of {} new submissions...'.format(self._NEW_SUBMISSION_LIMIT)
			for submission in new_submissions:
				self.total_submissions_seen += 1

				# Try and generate a comment for this URL
				url = submission.url
				comment_info = self.generate_comment(reddit, url, submission.fullname)

				# If we were given a comment, add it and log it
				if comment_info is not None and not submission.fullname in self.already_visited:
					comment_text, comment_score = comment_info[0], comment_info[1]
					self.reposts_seen += 1
					self.already_visited.add(submission.fullname)
					self.block_for(self._NORMAL_DELAY)
					submission.upvote()
					self.block_for(self._COMMENT_DELAY)
					# commenting can cause praw.errors.APIException (e.g. for a deleted link), so check for this
					submission.add_comment(comment_text)
					print '\tAdded a comment!'
					print '\tRepost rate: {}'.format(float(self.reposts_seen)/self.total_submissions_seen)
					logging.info('Added a comment to: {}'.format(submission.short_link))


	def is_comment(self, c):
		""" Simple wrapper for checking that a given object is a Comment object """
		if type(c) == praw.objects.Comment:
			return True
		else:
			return False

	def get_comments(self, obj):
		""" Takes in a Submission or MoreComments object and returns its comments """
		self.block_for(self._NORMAL_DELAY)
		if type(obj) == praw.objects.MoreComments:
			return obj.comments()
		elif type(obj) == praw.objects.Submission:
			return obj.comments

	# Both Submission and MoreComments objects have comments to process!
	def process_comments(self, obj_with_comments, current_top_score):
		""" Recursive function to find the top comment in a Submission's comments. Returns
		    a tuple of (text, score). """
		current_top_text = None

		for c in self.get_comments(obj_with_comments):
			if self.is_comment(c):
				if c.score > current_top_score:
					current_top_score = c.score
					current_top_text = c.body
			else:
				top_of_rest = process_comments(c, current_top_score)
				if top_of_rest[1] > current_top_score:
					current_top_text, current_top_score = top_of_rest[0], top_of_rest[1]

		return (current_top_text, current_top_score)

	def submission_too_young(self, s):
		if time() - s.created < self._SECONDS_PER_DAY:
			return True
		else:
			return False

	def generate_comment(self, reddit, url, orig_fullname):
		""" Given a PRAW Reddit object and a URL, returns a comment of the highest rated comment on all
		    submissions that use url (not including Submission with fullname == orig_fullname). If no 
		    submissions exist with the given URL, return None """
		# Get all submissions with the given URL
		self.block_for(self._NORMAL_DELAY)
		url_submissions = reddit.get_info(url=url, limit=15)

		# No posts contain the given URL, so return None
		if len(url_submissions) == 0:
			return None

		# Initialize the top comment data
		overall_top_score = 0
		overall_top_text = None

		# Go through all existing submissions and get the top comment
		for s in url_submissions:
			if s.fullname == orig_fullname or self.submission_too_young(s):
				continue

			# Extract top comment text / score from the existing submission
			top_comment_info = self.process_comments(s, 0)
			top_comment_text, top_comment_score = top_comment_info[0], top_comment_info[1]

			# If this is a new best comment, update the overall top comment data
			if top_comment_score > overall_top_score:
				overall_top_score = top_comment_score
				overall_top_text = top_comment_text

		if overall_top_text is None:
			return None
		else:
			return (overall_top_text, overall_top_score)

	def error(msg):
		""" Simple helper function that's called upon a fatal error. """
		print msg
		exit()

def usage():
	print "Usage: python bot.py subreddit username password"
	exit()

if __name__ == '__main__':
	if len(argv) != 4:
		usage()
	else:
		cs = CommentStealer(argv[1], argv[2], argv[3])
		cs.monitor()