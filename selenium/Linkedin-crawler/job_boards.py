from sqlalchemy import create_engine, Column, Integer, String, Text, Numeric, Date
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import requests

# Define the SQLAlchemy model
from sqlalchemy.pool import NullPool

Base = declarative_base()


class JobBoards(Base):
    __tablename__ = 'job_boards'
    job_id = Column(Text, primary_key=True)
    source = Column(Text)
    jobtitle = Column(Text)
    jobtype = Column(Text)
    joblocationcity = Column(Text)
    company = Column(Text)
    salary = Column(Text)
    link = Column(Text)
    posted = Column(Date)
    extracteddate = Column(Date)
    description = Column(Text)
    min_salary = Column(Numeric(10, 3))
    max_salary = Column(Numeric(10, 3))
    joblocationinput = Column(Text)


conn_string = 'postgresql://postgres:Asdf123!@jobsdb.ci86gncdfulv.eu-west-2.rds.amazonaws.com/postgres'

engine = create_engine(conn_string, poolclass=NullPool)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)


def remove_keys_not_in_list(dictionary, key_list):
  keys_to_remove = [key for key in dictionary.keys() if key not in key_list]
  for key in keys_to_remove:
    del dictionary[key]

# Example usage:
allowed_keys = JobBoards.__table__.columns.keys()


def insertJobBoardObject(job, searchName="NULL"):
    # Upsert the instance to the session
    try:
      session = Session()
      remove_keys_not_in_list(job, allowed_keys)
      job['company'] = job['company'].strip()
      new_record = JobBoards(**job)
      session.merge(new_record)
      session.commit()
    except Exception as e:
      print(e)
      session.rollback()
    finally:
      session.close()

    try:
      if job['job_id'] and job['jobtitle']:
        print(job['job_id'])
        print(job['jobtitle'])
        print(job['company'])
        # Add request to check notis here with location and job title
        url = "http://13.43.25.0:5001/job-search/checkout-new-jobs?location=" + job[
          'joblocationinput'] + "&searchName=" + searchName
        requests.get(url)
    except Exception:
        print("Can not call checkout new jobs")


