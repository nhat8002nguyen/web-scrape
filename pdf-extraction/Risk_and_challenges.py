from PyPDF2 import PdfReader
import os
from concurrent.futures import ThreadPoolExecutor, as_completed


def main() -> None:
	pdf_file_paths = []
	input_folder_path = os.path.join(os.getcwd(), "inputs")
	for root, dirs, files in os.walk(input_folder_path):
		for file_name in files:
			pdf_file_paths.append(os.path.join(input_folder_path, file_name))

	results = []
	tasks = []
	with ThreadPoolExecutor(max_workers=8) as pool:
		for path in pdf_file_paths:
			task = pool.submit(extract_file_data, path)
			tasks.append(task)

		for future in as_completed(tasks):
			results.append(future.result())				

	with open("./outputs/output.txt", 'w') as file_writer:	
		file_writer.write("\n\n".join(results))

def extract_file_data(file_path: str) -> str:
	'''This will extract the risk and chanllenges section and return output file name and data'''
	reader = PdfReader(file_path)
	number_of_pages = len(reader.pages)
	result = ""
	for i in range(number_of_pages):
		page = reader.pages[i]
		text = page.extract_text()

		start_text = "Risks and challenges"
		end_text = "FAQ"
		if start_text in text:
			start_index = text.index(start_text)
			if end_text in text:
				end_index = text.index(end_text)
				result = text[start_index:end_index]

	return result	


if __name__ == "__main__":
	main()
