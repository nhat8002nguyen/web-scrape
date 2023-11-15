# importing the module  
from pytube import YouTube  
  
# where to save  
SAVE_PATH = "D:/NhatNguyen/Temp files"   
  
# link of the video to be downloaded  
link="https://www.youtube.com/watch?v=xWOoBJUqlbI"
  
try:  
    # object creation using YouTube 
    # which was imported in the beginning  
    yt = YouTube(link)  
    yt.streams.filter(
        progressive=True, file_extension='mp4'
    ).order_by('resolution').desc().first().download(output_path=SAVE_PATH)
	
except:  
    print("Download error") #to handle exception  

print('Task Completed!')