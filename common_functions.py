# Copyright (c) 2024 Praneeth Vadlapati

import os
import time
import math

from datasets import get_dataset_config_names
from dotenv import load_dotenv
from groq import Groq
from IPython.display import display, Markdown
import pandas as pd

load_dotenv(override=True)  # bypass cache and reload the variables

dataset_name = 'HuggingFaceFW/fineweb'

data_name = dataset_name.split('/')[-1]  # get part after last /
folder = 'data'

# latest_dump_name = 'CC-MAIN-2024-18'  # set manually for now
latest_dump_file = os.path.join(folder, f'{data_name}-latest_dump.txt')
try:
	with open(latest_dump_file, 'r') as f:
		latest_dump_name = f.read().strip()
except:
	latest_dump_name = None

if not latest_dump_name:
	print('Fetching latest dump name...')
	versions = get_dataset_config_names(dataset_name)
	versions = [v for v in versions if v != 'default' and not v.startswith('sample')]
	latest_dump_name = sorted(versions, key=lambda x: x, reverse=True)[0]

# save latest dump name to file
with open(latest_dump_file, 'w') as f:
	f.write(latest_dump_name)

# create folder for saving csv files
data_dir = os.path.join(folder, f'{data_name}-{latest_dump_name}')
os.makedirs(data_dir, exist_ok=True)

ext = 'csv'
safe_flag = 'safe'

harm_categories = {
	'S1': 'Violent Crimes',
	'S2': 'Non-Violent Crimes',
	'S3': 'Sex-Related Crimes',
	'S4': 'Child Sexual Exploitation',
	'S5': 'Specialized Advice',
	'S6': 'Privacy',
	'S7': 'Intellectual Property',
	'S8': 'Indiscriminate Weapons',
	'S9': 'Hate',
	'S10': 'Suicide & Self-Harm',
	'S11': 'Sexual Content'
}
flags_list = [
	'sensitive_topic', 'biased', 'religious', 'lottery', 'scam', 
	'advertisement', 'data_poisoning_attack', # 'cheating_service', 'unethical', 
	'unusable', 
]
unwanted_flags = flags_list


def get_filename(index, process_type='full'):
	if process_type:
		process_type = f'.{process_type}'
	return os.path.join(data_dir, f'New_data - {index}{process_type}.{ext}')


def get_latest_index(process_type='full', empty_ok=False):
	last_index = None
	for index in range(1000):
		file_name = get_filename(index, process_type)
		if os.path.exists(file_name):
			last_index = index
		else:
			break
	if empty_ok and last_index is None:  # get empty filename
		return get_filename(0, process_type)
	return last_index


def get_latest_filename(process_type='filtered', empty_ok=False):
	last_file_path = None
	for index in range(1000):
		file_name = get_filename(index, process_type)
		if os.path.exists(file_name):
			last_file_path = file_name
		else:
			break
	if empty_ok and not last_file_path:  # get empty filename
		return get_filename(0, process_type)
	return last_file_path


def display_md(text):
	'Display markdown in notebooks'
	if not text:
		return
	try:
		text = text.replace('\n', '<br>')
		display(Markdown(text))
	except:
		display(Markdown('_Error displaying text_'))
		print(text)


def extract_backtick_data(response):
	# replace single backticks with triple backticks
	if '```' not in response:
		response = response.replace('`', '```')
	response = response.replace('```\n```', '```')
	# get the value from triple backticks
	response = response.split('```')[1]
	if response.startswith('csv'):  # remove 'csv' from start of backticks
		response = response[3:].strip()
	return response.strip()

groq_client = Groq()
groq_model_main = os.getenv('GROQ_MODEL')
alternative_model = os.getenv('GROQ_ALTERNATIVE_MODEL')
# alternative_model_2 = os.getenv('GROQ_ALTERNATIVE_MODEL_2')

groq_model = groq_model_main
tried_all_models = False

def print_modelname():
	print(f'Model: {groq_model}')


def get_bot_response(messages, process_backticks=False, max_retries=4):
	global groq_model, tried_all_models, groq_model_main, alternative_model #, alternative_model_2
	for _ in range(max_retries):
		try:
			chat_completion = groq_client.chat.completions.create(
				messages=messages,
				model=groq_model,
			)
			response = chat_completion.choices[0].message.content
			response = response.strip()
			if not response:
				raise Exception('Empty response from the bot')
			if process_backticks:
				response = extract_backtick_data(response)
			return response
		except Exception as e:
			e = str(e)
			if '429' in e:  # Rate limit
				# get text '23' from e='... Please try again in 23m3.714445312s. ...'
				rate_limit_time = e.split('Please try again in')[1].split('. Visit')[0].strip()
				rate_limit_time_min = rate_limit_time.split('m')[0]  # rate_limit_time = '1m20s'
				rate_limit_time_sec = rate_limit_time.split('m')[1].split('s')[0]
				total_wait_time = 0
				if 'm' in rate_limit_time:
					total_wait_time += int(rate_limit_time_min) * 60
				if 's' in rate_limit_time:
					total_wait_time += int(rate_limit_time_sec)
				print(f'Rate Limit reached for {rate_limit_time}', end='')
				if tried_all_models:
					print('Waiting...')
					time.sleep(total_wait_time)
					continue
				if alternative_model and len(alternative_model):
					if groq_model != alternative_model:
						groq_model = alternative_model
						print(f'Rate limit reached. Trying with {groq_model}')
						tried_all_models = False
						continue
				else:
					print('Waiting...')
					time.sleep(total_wait_time)
					continue
				# if alternative_model_2 and groq_model != alternative_model_2:
				# 	groq_model = alternative_model_2
				# 	print(f'Rate limit reached. Trying with {groq_model}')
				# 	tried_all_models = False
				# 	continue
				if groq_model != groq_model_main:  # Finally try using new model
					groq_model = groq_model_main
					print(f'Rate limit reached. Trying with {groq_model}')
					tried_all_models = True
					continue
			print(f'Error: {e}. Retrying')
	raise Exception('No response from the bot')



def print_progress():
	print('.', end='', flush=True)

def print_error(err=None):
	print('!', end='', flush=True)

def is_na(val) -> bool:
	if not val:
		return True
	if isinstance(val, float) and math.isnan(val):
		return True
	if pd.isna(val):
		return True
	return False

def is_not_na(val) -> bool:
	return not is_na(val) and val != safe_flag



