from flask import Flask, request, render_template, send_file
import os
import pandas as pd
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from werkzeug.utils import secure_filename
import zipfile

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'static/output'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

def scrape_products(domain):
    try:
        url = f"http://{domain}"
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')

        product_cards = soup.select('.product-card')[:3]
        products = []
        for card in product_cards:
            image_url = card.select_one('img')['src']
            name = card.select_one('.product-title').text.strip()
            price = card.select_one('.product-price').text.strip()
            products.append({'image_url': image_url, 'name': name, 'price': price})
        return products
    except Exception as e:
        print(f"Error scraping {domain}: {e}")
        return None

def create_image(domain_name, products, output_size):
    try:
        template = Image.new('RGB', output_size, 'white')
        draw = ImageDraw.Draw(template)
        try:
            title_font = ImageFont.truetype("arial.ttf", 50)
            text_font = ImageFont.truetype("arial.ttf", 30)
        except IOError:
            title_font = text_font = ImageFont.load_default()

        draw.rectangle([(0, 0), (output_size[0], 80)], fill="black")
        draw.text((output_size[0] // 2, 20), domain_name, fill="white", font=title_font, anchor="mm")
        draw.text((output_size[0] // 2, 100), "Best sellers", fill="black", font=title_font, anchor="mm")

        product_width = output_size[0] // 4
        product_height = output_size[1] // 2
        x_start = (output_size[0] - product_width * 3) // 2
        y_start = 150
        padding = 50

        for i, product in enumerate(products):
            x_offset = x_start + (product_width + padding) * i
            img_response = requests.get(product['image_url'])
            product_img = Image.open(BytesIO(img_response.content)).resize((product_width, product_height))
            template.paste(product_img, (x_offset, y_start))
            draw.text((x_offset + product_width // 2, y_start + product_height + 10), product['name'], fill="black", font=text_font, anchor="mm")
            draw.text((x_offset + product_width // 2, y_start + product_height + 50), product['price'], fill="black", font=text_font, anchor="mm")

        return template
    except Exception as e:
        print(f"Error creating image for {domain_name}: {e}")
        return None

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        file = request.files['file']
        if file:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
            file.save(filepath)
            output_zip = process_domains(filepath)
            return send_file(output_zip, as_attachment=True)
    return render_template('upload.html')

def process_domains(filepath):
    df = pd.read_excel(filepath)
    domains = df['domain'].dropna().tolist()
    zip_filename = os.path.join(app.config['OUTPUT_FOLDER'], 'output_images.zip')

    with zipfile.ZipFile(zip_filename, 'w') as zipf:
        for domain in domains:
            print(f"Processing {domain}...")
            products = scrape_products(domain)
            if not products:
                print(f"Skipping {domain} due to scraping issues.")
                continue

            for size in [(1200, 1200), (1200, 628)]:
                image = create_image(domain, products, size)
                if image:
                    size_folder = f"{domain}_{size[0]}x{size[1]}.png"
                    image_path = os.path.join(app.config['OUTPUT_FOLDER'], size_folder)
                    image.save(image_path)
                    zipf.write(image_path, arcname=f"{domain}/{size_folder}")

    return zip_filename

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
