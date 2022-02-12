import time
import re
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec


def xfinity_test(driver):
    print("Xfinity Speed Test Running...")

    speeds = []

    # open xfinity on Google Chrome
    driver.get("https://speedtest.xfinity.com/")

    # chrome put in "background"
    # driver.set_window_position(-10000, 0)

    # Make sure we're on the right page
    assert "Xfinity" in driver.title

    # click button to start speed test
    elem = driver.find_element(By.XPATH, "/html[1]/body[1]/div[1]/div[2]/div[1]/div[1]/div[1]/div[1]/button[1]")
    elem.click()

    print("Calculating Download Speed...")

    # wait until download speed is done to capture value
    WebDriverWait(driver, 20).until(ec.presence_of_element_located((By.XPATH, "/html/body/div[1]/div[2]/details/summary/div/dl/dd")))
    elem = driver.find_element(By.XPATH, "/html/body/div[1]/div[2]/details/summary/div/dl/dd")
    speeds.append(float(re.findall(r"[0-9]*[.,][0-9]*", elem.text)[0]))

    # wait until upload speed is done to capture value
    elem = driver.find_element(By.XPATH, "/html/body/div[1]/div[2]/details/summary/div/div/p")
    elem.click()
    print("Calculating Upload Speed...")
    time.sleep(14)

    # upload speed
    elem = driver.find_element(By.XPATH, "/html/body/div[1]/div[2]/details/div/div/dl/div[1]/dd")
    speeds.append(float(re.findall(r"[0-9]*[.,][0-9]*", elem.text)[0]))

    return speeds


def fastdotcom_test(driver):
    print("Fast.com speed test running...")
    speeds = []

    driver.get("https://fast.com/")

    print("Calculating Download Speed...")
    time.sleep(10)

    elem = driver.find_element(By.XPATH, "//*[@id='speed-value']")
    speeds.append(float(elem.text))

    elem = driver.find_element(By.XPATH, "//*[@id='show-more-details-link']")
    elem.click()
    print("Calculating Upload Speed...")
    time.sleep(8)

    elem = driver.find_element(By.XPATH, "//*[@id='upload-value']")
    speeds.append(float(elem.text))

    time.sleep(7)

    return speeds


def speedtestdotnet(driver):
    print("Speedtest.net speed test running...")
    speeds = []

    driver.get("https://www.speedtest.net/")

    elem = driver.find_element(By.XPATH, "//*[@id='container']/div/div[3]/div/div/div/div[2]/div[3]/div[1]/a/span[4]")
    elem.click()

    print("Calculating Download Speed...")
    time.sleep(22)
    print("Calculating Upload Speed...")
    time.sleep(21)

    elem = driver.find_element(By.XPATH, "//*[@id='container']/div/div[3]/div/div/div/div[2]/div[3]/div[3]/div/div[3]/div/div/div[2]/div[1]/div[2]/div/div[2]/span")
    speeds.append(float(re.findall(r"[0-9]*[.,][0-9]*", elem.text)[0]))

    elem = driver.find_element(By.XPATH, "//*[@id='container']/div/div[3]/div/div/div/div[2]/div[3]/div[3]/div/div[3]/div/div/div[2]/div[1]/div[3]/div/div[2]/span")
    speeds.append(float(re.findall(r"[0-9]*[.,][0-9]*", elem.text)[0]))

    return speeds


if __name__ == "__main__":
    s = Service(ChromeDriverManager().install())
    # use chrome
    driver = webdriver.Chrome(service=s)

    summary = []
    xfin = xfinity_test(driver)
    fast = fastdotcom_test(driver)
    speed = speedtestdotnet(driver)

    driver.quit()

    summary.append((xfin[0] + fast[0] + speed[0]) / 3)
    summary.append((xfin[1] + fast[1] + speed[1]) / 3)

    print(" \n================== Xfinity Speed Test ==================",
          "Download: {}".format(xfin[0]),
          "Upload: {}\n".format(xfin[1]),
          "================== Fast.com Speed Test ==================",
          "Download: {}".format(fast[0]),
          "Upload: {}\n".format(fast[1]),
          "================== Speedtest.net Speed Test ==================",
          "Download: {}".format(speed[0]),
          "Upload: {}\n".format(speed[1]),
          "================== SUMMARY ==================",
          "Average Download Speed: {} Mbps".format(summary[0]),
          "Average Upload Speed: {} Mbps".format(summary[1]),
          sep='\n'
          )






