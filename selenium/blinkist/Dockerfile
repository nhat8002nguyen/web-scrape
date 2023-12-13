FROM python:3.10

WORKDIR "/docker-dir/blinkist/"
COPY "./main.py" "/docker-dir/blinkist/"

RUN pip install pandas python-dotenv selenium seleniumbase undetected_chromedriver openpyxl

RUN apt-get install -y wget
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
# Chrome dependency Instalation 
RUN apt-get update && apt-get install -y \     
	fonts-liberation \     
	libasound2 \     
	libatk-bridge2.0-0 \     
	libatk1.0-0 \     
	libatspi2.0-0 \     
	libcups2 \     
	libdbus-1-3 \     
	libdrm2 \     
	libgbm1 \     
	libgtk-3-0 \ 
#    	libgtk-4-1 \     
	libnspr4 \     
	libnss3 \     
	libwayland-client0 \     
	libxcomposite1 \     
	libxdamage1 \     
	libxfixes3 \     
	libxkbcommon0 \     
	libxrandr2 \     
	xdg-utils \     
	libu2f-udev \     
	libvulkan1  
# Chrome instalation

RUN apt-get install -y ./google-chrome-stable_current_amd64.deb

CMD ["python", "/docker-dir/blinkist/main.py"]
