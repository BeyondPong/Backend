from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from django.test import LiveServerTestCase


# Create your tests here.
class WebSocketTests(LiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.driver = webdriver.Chrome()

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()
        super().tearDownClass()

    def test_user_websocket(self):
        self.driver.get(self.live_server_url + "/user/")

        user_id_input = self.driver.find_element(By.ID, "user-id-input")
        user_id_input.send_keys("user1")
        user_id_input.send_keys(Keys.ENTER)

        status_message_input = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "status-message-input"))
        )
        status_message_input.send_keys("active")
        status_message_input.send_keys(Keys.ENTER)

        status_log = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located(By.ID, "status-log")
        )
        self.assertIn("active", status_log.get_attribute("value"))
