from html2image import Html2Image
hti = Html2Image(output_path='shop_images', browser='chrome')
hti.screenshot(html_str='<h1 style="color:red">Test OK</h1>', save_as='_test.png', size=(400, 200))
print('OK - check shop_images/_test.png')
