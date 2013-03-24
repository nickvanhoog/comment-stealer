import praw
from sys import argv, exit
from pprint import pprint
import logging
from time import time as time

NEW_SUBMISSION_LIMIT = 50
LOG_FILENAME = 'botlog.log'
SECONDS_PER_DAY = 86400
last_request_time = 0
NORMAL_DELAY = 2
COMMENT_DELAY = 30
total_submissions_seen = 0
reposts_seen = 0

def block_for(wait_time):
	global last_request_time
	while time() - last_request_time < wait_time:
		continue
	last_request_time = time()

def monitor():
	""" Monitors new posts in the given subreddit, detects reposts of the same link, 
	    finds the top comment in all previous posts, and adds a comment whose body
	    is the body of aforementioned top comment. """
	logging.basicConfig(filename=LOG_FILENAME, level=logging.INFO)
	last_request_time = 0
	already_visited = []

	# Get command line arguments
	subreddit_name = argv[1]
	username = argv[2]
	pw = argv[3]
	user_agent = 'stealstopcomments by /u/StealsTopComments'


	# Log in
	try:
		r = praw.Reddit(user_agent=user_agent)
		r.login(username, pw)
	except praw.errors.InvalidUserPass:
		error('***** ERROR: Invalid username or password *****')

	subreddit = r.get_subreddit(subreddit_name)

	# Continuously monitor the subreddit
	while True:
		block_for(NORMAL_DELAY)
		new_submissions_gen = subreddit.get_new(limit=NEW_SUBMISSION_LIMIT)

		# Iterating over new submissions
		print 'Checking batch of new submissions...'
		for s in new_submissions_gen:
			global total_submissions_seen
			total_submissions_seen += 1
			# Try and generate a comment for this URL
			url = s.url
			comment_text = generate_comment(r, url, s.fullname)

			# If we were given a comment, add it and log it
			if comment_text is not None and not s.fullname in already_visited:
				global reposts_seen
				reposts_seen += 1
				already_visited.append(s.fullname)
				block_for(NORMAL_DELAY)
				s.upvote()
				block_for(COMMENT_DELAY)
				s.add_comment(comment_text)
				print '\tAdded a comment!'
				print '\tRepost rate: {}'.format(float(reposts_seen)/total_submissions_seen)
				logging.info('Added a comment to: {}'.format(s.short_link))


def is_comment(c):
	""" Simple wrapper for checking that a given object is a Comment object """
	if type(c) == praw.objects.Comment:
		return True
	else:
		return False

def get_comments(obj):
	""" Takes in a Submission or MoreComments object and returns its comments """
	block_for(NORMAL_DELAY)
	if type(obj) == praw.objects.MoreComments:
		return obj.comments()
	elif type(obj) == praw.objects.Submission:
		return obj.comments

# Both Submission and MoreComments objects have comments to process!
def process_comments(obj_with_comments, current_top_score):
	""" Recursive function to find the top comment in a Submission's comments. Returns
	    a tuple of (text, score). """
	current_top_text = None

	for c in get_comments(obj_with_comments):
		if is_comment(c):
			if c.score > current_top_score:
				current_top_score = c.score
				current_top_text = c.body
		else:
			top_of_rest = process_comments(c, current_top_score)
			if top_of_rest[1] > current_top_score:
				current_top_text, current_top_score = top_of_rest[0], top_of_rest[1]

	return (current_top_text, current_top_score)

def submission_too_young(s):
	if time() - s.created < SECONDS_PER_DAY:
		return True
	else:
		return False

def generate_comment(reddit, url, orig_fullname):
	""" Given a PRAW Reddit object and a URL, returns a comment of the highest rated comment on all
	    submissions that use url (not including Submission with fullname == orig_fullname). If no 
	    submissions exist with the given URL, return None """
	# Get all submissions with the given URL
	block_for(NORMAL_DELAY)
	url_submissions = reddit.get_info(url=url, limit=15)

	# No posts contain the given URL, so return None
	if len(url_submissions) == 0:
		return None

	# Initialize the top comment data
	overall_top_score = 0
	overall_top_text = None

	# Go through all existing submissions and get the top comment
	for s in url_submissions:
		if s.fullname == orig_fullname or submission_too_young(s):
			continue

		# Extract top comment text / score from the existing submission
		top_comment_info = process_comments(s, 0)
		top_comment_text, top_comment_score = top_comment_info[0], top_comment_info[1]

		# If this is a new best comment, update the overall top comment data
		if top_comment_score > overall_top_score:
			overall_top_score = top_comment_score
			overall_top_text = top_comment_text

	return overall_top_text

def usage():
	print "Usage: python bot.py subreddit username password"
	exit()

def error(msg):
	print msg
	exit()

if __name__ == '__main__':
	if len(argv) != 4:
		usage()
	else:
		monitor()