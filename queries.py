import os
import shutil

from elasticsearch import Elasticsearch, exceptions
import json
import time
import nltk
import write_to_csv as write
import data_visualization as visualize
from nltk.util import ngrams
from nltk.corpus import stopwords
from collections import Counter

stop_words = stopwords.words('english')

DOMAIN = "localhost"
PORT = 9200

query_response = []
all_tweets = []
tweets_per_month = {}
tweets_per_location = {}
tweets_per_day = {}
tweets_per_user = {}
tweets_per_hour = {}
tweets_per_hour_per_day = {}


def create_es_client():
    # concatenate a string for the client's host paramater
    host = str(DOMAIN) + ":" + str(PORT)

    # declare an instance of the Elasticsearch library
    client = Elasticsearch(host, timeout=5000, max_retries=1000, retry_on_timeout=True)

    try:
        # use the JSON library's dump() method for indentation
        info = json.dumps(client.info(), indent=4)

        # pass client object to info() method
        # print("Elasticsearch client info():", info)

    except exceptions.ConnectionError as err:

        # print ConnectionError for Elasticsearch
        print("\nElasticsearch info() ERROR:", err)
        print("\nThe client host:", host, "is invalid or cluster is not running")

        # change the client's value to 'None' if ConnectionError
        client = None

    return client


# Create a function to see if the tweet is a retweet
def is_RT(tweet):
    if 'retweeted_status' not in tweet:
        return False
    else:
        return True


# Create a function to see if the tweet is a reply to a tweet of #another user, if so return said user.
def is_Reply_to(tweet):
    if 'in_reply_to_screen_name' not in tweet:
        return False
    else:
        return tweet['in_reply_to_screen_name']


# Create function for taking the most used Tweet sources off the #source column
def reckondevice(tweet):
    if 'iPhone' in tweet['source'] or ('iOS' in tweet['source']):
        return 'iPhone'
    elif 'Android' in tweet['source']:
        return 'Android'
    elif 'Mobile' in tweet['source'] or ('App' in tweet['source']):
        return 'Mobile device'
    elif 'Mac' in tweet['source']:
        return 'Mac'
    elif 'Windows' in tweet['source']:
        return 'Windows'
    elif 'Bot' in tweet['source']:
        return 'Bot'
    elif 'Web' in tweet['source']:
        return 'Web'
    elif 'Instagram' in tweet['source']:
        return 'Instagram'
    elif 'Blackberry' in tweet['source']:
        return 'Blackberry'
    elif 'iPad' in tweet['source']:
        return 'iPad'
    elif 'Foursquare' in tweet['source']:
        return 'Foursquare'
    else:
        return '-'


def get_date(timestamp):
    # Sun Dec 01 08:56:40 +0000 2019
    date = {}
    t = timestamp.split(" ")
    date['day'] = t[0]
    date['month'] = t[1]
    date['day_n'] = t[2]
    date['hour'] = (t[3].split(":"))[0]
    date['year'] = t[5]

    return date


def process_hour(timestamp):
    # Sun Dec 01 08:56:40 +0000 2019
    date = get_date(timestamp)

    key = date['month'] + " " + date['year']

    # tweets per day
    c_day = date['day_n'] + " " + date['day']
    if key in tweets_per_day:
        if c_day in tweets_per_day[key]:
            tweets_per_day[key][c_day] += 1
        else:
            tweets_per_day[key][c_day] = 1
    else:
        tweets_per_day[key] = {c_day: 1}

    # tweets per hour
    hour = date['hour']
    if key in tweets_per_hour:
        if hour in tweets_per_hour[key]:
            tweets_per_hour[key][hour] += 1
        else:
            tweets_per_hour[key][hour] = 1
    else:
        tweets_per_hour[key] = {hour: 1}

    if key in tweets_per_hour_per_day:
        if c_day in tweets_per_hour_per_day[key]:
            if hour in tweets_per_hour_per_day[key][c_day]:
                tweets_per_hour_per_day[key][c_day][hour] += 1
            else:
                tweets_per_hour_per_day[key][c_day][hour] = 1
        else:
            tweets_per_hour_per_day[key][c_day] = {hour: 1}
    else:
        tweets_per_hour_per_day[key] = {c_day: {hour: 1}}


def retweeted_perc(tweets):
    start = time.time()

    # See the percentage of tweets from the initial set that are #retweets:
    RT_tweets = tweets[tweets['retweeted_status'] == True]
    print("The percentage of retweets is" + str({round(len(RT_tweets) / len(tweets) * 100)}) + "% of all the tweets")

    end = time.time()
    print("Time to perform the query: " + str(end - start))


def process_hits(hits, index):
    for item in hits:
        # print(json.dumps(item, indent=2))

        tweets_per_month[index] += 1

        user = item['_source']['user']
        username = user['screen_name']
        location = user['location']

        if username in tweets_per_user:
            tweets_per_user[username] += 1
        else:
            tweets_per_user[username] = 1

        if location in tweets_per_location:
            tweets_per_location[location] += 1
        else:
            tweets_per_location[location] = 1

        # TWEETS PER HOUR
        created_at = item['_source']['created_at']
        process_hour(created_at)


def get_text_and_date(hits):
    for item in hits:
        text_and_date = []
        text = item['_source']['text']
        date = item['_source']['created_at']

        text_and_date.append(text)
        text_and_date.append(date)

        all_tweets.append(text_and_date)


def search(client, search_body, query_num):
    global query_response
    # get all of the indices on the Elasticsearch cluster
    all_indices = client.indices.get_alias("*")

    for num, index in enumerate(all_indices):
        if "all_" in index:
            continue
        if "." in index:
            continue

        print("Index:" + index)
        resp = client.search(
            index=index,
            # doc_type="_doc",
            scroll="30m",
            # search_type="scan",
            size=1000,
            body=search_body
        )

        scroll_id = resp['_scroll_id']

        scroll_size = len(resp['hits']['hits'])

        # Start scrolling
        while scroll_size > 0:
            "Scrolling..."
            # Before scroll, process current batch of hits
            #if query_num == 1:
            process_hits(resp['hits']['hits'], index)

            #if query_num == 2:
            get_text_and_date(resp['hits']['hits'])

            resp = client.scroll(scroll_id=scroll_id, scroll='30m')

            query_response.append(resp['hits']['hits'])

            # Update the scroll ID
            scroll_id = resp['_scroll_id']

            # Get the number of results that returned in the last scroll
            scroll_size = len(resp['hits']['hits'])


def match_all(client):
    search_body = {
        "query": {
            "match_all": {
            }
        }
    }
    search(client, search_body)


def filter_keyword(client, keyword, query_num):
    search_body = {
        "query": {
            "match": {
                "text": {
                    "query": keyword
                }
            }
        }
    }
    search(client, search_body, query_num)


def filter_phrase(client, phrase, query_num):
    search_body = {
        "query": {
            "match_phrase": {
                "text": phrase
            }
        }
    }
    search(client, search_body, query_num)


def initialise_dicts(client):
    # get all of the indices on the Elasticsearch cluster
    all_indices = client.indices.get_alias("*")
    for num, index in enumerate(all_indices):
        tweets_per_month[index] = 0


def analyse_keyword(client, keyword, query_num):
    k_list = keyword.split(" ")
    if len(k_list) > 1:
        print("Filtering phrase")
        filter_phrase(client, keyword, query_num)
    else:
        print("Filtering keyword")
        filter_keyword(client, keyword, query_num)

def term_occurence(all_tweets, keyword, year, month, day, hour):
    myfolder = "results/"

    all_unigrams = []
    all_bigrams = []
    all_trigrams = []

    n_words = 20

    for item in all_tweets:
        tweet = item[0]
        tokens = nltk.word_tokenize(tweet)
        # convert to lower case
        tokens = [w.lower() for w in tokens]

        # remove punctuation from each word
        import string
        table = str.maketrans('', '', string.punctuation)
        stripped = [w.translate(table) for w in tokens]

        # remove remaining tokens that are not alphabetic
        words = [word for word in stripped if word.isalpha()]

        # filter out stop words
        words = [w for w in words if not w in stop_words]

        all_unigrams.extend(ngrams(words, 1))
        all_bigrams.extend(ngrams(words, 2))
        all_trigrams.extend(ngrams(words, 3))

    word_freq = Counter(all_unigrams)
    common_words = word_freq.most_common(n_words)
    filename = "unigrams" + ".csv"
    write.list_to_csv(myfolder, common_words, filename, year, month, day, hour)

    bigram_freq = Counter(all_bigrams)
    common_bigrams = bigram_freq.most_common(n_words)
    filename = "bigrams" + ".csv"
    write.list_to_csv(myfolder, common_bigrams, filename, year, month, day, hour)

    trigram_freq = Counter(all_trigrams)
    common_trigrams = trigram_freq.most_common(n_words)
    filename = "trigrams" + ".csv"
    write.list_to_csv(myfolder, common_trigrams, filename, year, month, day, hour)


def filter_by_date(tweets, year_to_filter, month_to_filter=-1, day_to_filter=-1, hour_to_filter=-1):
    filtered_tweets = []
    for item in tweets:
        date = get_date(item[1])
        year = date['year']
        month = date['month']
        day_n = date['day_n']
        hour = date['hour']

        y_append = 1
        m_append = 1
        d_append = 1
        h_append = 1

        if year_to_filter != -1 and year != year_to_filter:
            y_append = 0

        if month_to_filter != -1 and month != month_to_filter:
            m_append = 0

        if day_to_filter != -1 and day_n != day_to_filter:
            d_append = 0

        if hour_to_filter != -1 and hour != hour_to_filter:
            h_append = 0

        if y_append and m_append and d_append and h_append:
            filtered_tweets.append(item)

    return filtered_tweets


def term_occurence_over_time(keyword, year=-1, month=-1, day=-1, hour=-1):
    global all_tweets
    filtered_tweets = filter_by_date(all_tweets, year, month, day, hour)

    print("Total tweets in the selected period: " + str(len(filtered_tweets)))
    term_occurence(filtered_tweets, keyword, year, month, day, hour)

def remove(path):
    """ param <path> could either be relative or absolute. """
    if os.path.isfile(path):
        os.remove(path)  # remove the file
    elif os.path.isdir(path):
        shutil.rmtree(path)  # remove dir and all contains
    else:
        print("Dir not found")

def write_results(keyword):
    ## Get input ##
    myfolder = "results/"

    ## Try to delete the file ##
    try:
        remove(myfolder)
        os.mkdir(myfolder)
    except OSError as e:  ## if failed, report it back to the user ##
        print("Error: %s - %s." % (e.filename, e.strerror))

    write.sorted_dict(myfolder, "tweets_per_month", tweets_per_month, keyword)
    write.sorted_dict(myfolder, "tweets_per_location", tweets_per_location, keyword)
    write.sorted_dict(myfolder, "tweets_per user", tweets_per_user, keyword)
    write.tweets_per_day(myfolder, tweets_per_day, keyword)
    write.tweets_per_hour(myfolder, tweets_per_hour_per_day, keyword)


def check_year(year):
    if year == "n":
        return -1
    return year


def check_month(month):
    if month == "n":
        return -1
    return month


def check_day(day):
    if day == "n":
        return -1
    return day


def check_hour(hour):
    if hour == "n":
        return -1
    return hour


def initialise_tweets():
    global all_tweets
    all_tweets = []

def query_analyse(which_query, keyword=None):
    client = create_es_client()

    if client is not None:
        initialise_dicts(client)
        start_time = time.time()

        if which_query == "filter":
            analyse_keyword(client, keyword, 1)
            write_results(keyword)

        end_time = time.time()
        print("\n\n\n\nQuery duration: " + str(end_time - start_time) + " seconds")

def query_occurence(keyword, year=-1, month=-1, day=-1, hour=-1):
    client = create_es_client()

    if client is not None:
        initialise_dicts(client)
        start_time = time.time()
        year = check_year(year)
        month = check_month(month)
        day = check_day(day)
        hour = check_hour(hour)
        initialise_tweets()
        analyse_keyword(client, keyword, 2)
        term_occurence_over_time(keyword, year, month, day, hour)

        end_time = time.time()
        print("\n\n\n\nQuery duration: " + str(end_time - start_time) + " seconds")
