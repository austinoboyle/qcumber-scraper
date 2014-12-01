#!/usr/bin/env python
import logging
import yaml
import sys
from navigation import SolusSession

def str_unless_none(obj):
    """Convert an object to a string unless it's None"""
    if obj is not None:
        return str(obj)
    return obj

def iterkeyvalue(obj):
    """Make it easy to iterate over dicts, lists, and strings"""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield str_unless_none(k), v
    elif isinstance (obj, list):
        for x in obj:
            yield str_unless_none(x), None
    else:
        yield str_unless_none(obj), None

def get_filter(obj):
    """Pick out the list of objects to filter by from a config item"""
    if obj is None:
        return [] # Empty list = accept nothing (optimized in the parser)
    elif hasattr(obj, "keys"):
        return list(map(str, obj.keys()))
    elif isinstance(obj, list):
        return list(map(str, obj))
    else:
        return tuple(str(obj))

class TestUpdater(object):
    """Dump HTML and the scraped data"""

    def __init__(self, config_file, user, passwd):
        """Initialize the session to grab the data with"""

        # Load the config
        self.load_config(config_file)

        # Initialize the session
        try:
            session = SolusSession(user, passwd)
            pass
        except EnvironmentError as e:
            logging.critical("Couldn't log in, can't update tests")
            raise

        self.session = session

    def load_config(self, config_file):
        """Load the config file"""
        try:
            with open(config_file) as f:
                self.config = yaml.load(f.read())
        except EnvironmentError as e:
            logging.critical("Couldn't load config file '{}'".format(config_file))
            raise

    def start(self):
        """Starts updating the local data"""

        logging.info("Starting update")
        self.scrape_alphanums()

    def scrape_alphanums(self):
        """Scrape alphanums"""

        all_alphanums = list(self.session.parser.all_alphanums(filter_=get_filter(self.config)))

        for alphanum, subjects in iterkeyvalue(self.config):

            if alphanum not in all_alphanums:
                logging.warning("Couldn't find alphanum {} specified in config file".format(alphanum))
                continue
            self.session.select_alphanum(alphanum)

            logging.info("Alphanum: {}".format(alphanum))

            self.scrape_subjects(subjects)

    def scrape_subjects(self, subjects):
        """Scrape subjects"""

        # Get a list of all subjects to iterate over
        parsed_subjects = self.session.parser.all_subjects(filter_=get_filter(subjects))
        # Index by abbreviation
        all_subjects = {x["abbreviation"]: x for x in parsed_subjects}

        # Iterate over all subjects
        for subject, courses in iterkeyvalue(subjects):

            curr_subject = all_subjects.get(subject)
            if curr_subject is None:
                if subject is not None:
                    logging.warning("Couldn't find subject {} specified in config file".format(subject))
                continue

            logging.info(u"--Subject: {abbreviation} - {title}".format(**curr_subject))

            self.session.dropdown_subject(curr_subject["_unique"])
            self.scrape_courses(courses)
            self.session.rollup_subject(curr_subject["_unique"])

    def scrape_courses(self, courses):
        """Scrape courses"""

        # Get a list of all courses to iterate over
        parsed_courses = self.session.parser.all_courses(filter_=get_filter(courses))
        # Index by code
        all_courses = {x["code"]: x for x in parsed_courses}

        # Iterate over all courses
        for course, terms in iterkeyvalue(courses):

            curr_course = all_courses.get(course)
            if curr_course is None:
                if course is not None:
                    logging.warning("Couldn't find course {} specified in config file".format(course))
                continue

            self.session.open_course(curr_course["_unique"])

            course_attrs = self.session.parser.course_attrs()
            logging.info(u"----Course: {number} - {title}".format(**course_attrs['basic']))
            logging.debug(u"COURSE DATA DUMP: {0}".format(course_attrs['extra']))

            self.session.show_sections()
            self.scrape_terms(terms)
            self.session.return_from_course()

    def scrape_terms(self, terms):
        """Scrape terms"""

        # Get all terms on the page and iterate over them
        parsed_terms = self.session.parser.all_terms(filter_=get_filter(terms))
        all_terms = {"{year} {season}".format(**x): x for x in parsed_terms}

        for term, sections in iterkeyvalue(terms):
            curr_term = all_terms.get(term)
            if curr_term is None:
                if term is not None:
                    logging.warning("Couldn't find term {} specified in config file".format(term))
                continue

            logging.info(u"------Term: {year} - {season}".format(**curr_term))
            self.session.switch_to_term(curr_term["_unique"])

            self.session.view_all_sections()
            self.scrape_sections(sections)

    def scrape_sections(self, sections):
        """Scrape sections"""

        # Grab all the basic data
        parsed_sections = self.session.parser.all_section_data(filter_=get_filter(sections))
        all_sections = {x["basic"]["solus_id"]: x for x in parsed_sections}

        # Don't really need the `iterkeyvalue` but it makes the config
        # parsing a litte more lax so whatever
        for section, _ in iterkeyvalue(sections):

            curr_section = all_sections.get(section)
            if curr_section is None:
                if section is not None:
                    logging.warning("Couldn't find section {} specified in config file".format(section))
                continue

            logging.info(u"--------Section: {class_num}-{type} ({solus_id}) -- {status}".format(**curr_section["basic"]))

            self.session.visit_section_page(curr_section["_unique"])

            new_data = self.session.parser.section_deep_attrs()
            logging.info(u"----------Section details: session:{session} loc:{location} campus:{campus}".format(**new_data["details"]))

            self.session.return_from_section()


def _init_logging():

    root_logger = logging.getLogger()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("[%(asctime)s][%(levelname)s][%(processName)s]: %(message)s"))
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)

    logging.getLogger("requests").setLevel(logging.WARNING)


if __name__ == "__main__":

    _init_logging()

    # Get credientials
    try:
        from config import USER, PASS
    except ImportError:
        logging.critical("No credientials found. Create a config.py file with USER and PASS constants")

    TestUpdater("tests/testconfig.yaml", USER, PASS).start()
