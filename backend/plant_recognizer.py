import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers, models
from tensorflow.keras.applications import MobileNetV2
import numpy as np

# 1. Load the Data
# This automatically looks at your folder names to create the 1081 classes
train_ds = tf.keras.utils.image_dataset_from_directory(
    'path/to/train',
    validation_split=0.2,
    subset="training",
    seed=123,
    image_size=(224, 224),
    batch_size=32,
    label_mode='categorical' 
)

class_names = train_ds.class_names

val_ds = tf.keras.utils.image_dataset_from_directory(
    'path/to/train',
    validation_split=0.2,
    subset="validation",
    seed=123,
    image_size=(224, 224),
    batch_size=32,
    label_mode='categorical'
)

AUTOTUNE = tf.data.AUTOTUNE
train_ds = train_ds.cache().prefetch(buffer_size=AUTOTUNE)
val_ds = val_ds.cache().prefetch(buffer_size=AUTOTUNE)

# 2. Define Augmentation Layers
data_augmentation = keras.Sequential([
  layers.RandomFlip("horizontal"),
  layers.RandomRotation(0.2),
  layers.RandomZoom(0.1),
])

# 3. Build the Model
base_model = MobileNetV2(weights='imagenet', include_top=False, input_shape=(224, 224, 3))
base_model.trainable = False 

model = models.Sequential([
    layers.Input(shape=(224, 224, 3)),
    data_augmentation,           
    layers.Rescaling(1./255),
    base_model,
    layers.GlobalAveragePooling2D(),
    layers.Dropout(0.2),
    layers.Dense(1081, activation='sigmoid')
])

model.compile(
    optimizer='adam',
    loss='binary_crossentropy',
    metrics=['binary_accuracy', tf.keras.metrics.TopKCategoricalAccuracy(k=5)]
)

def identify_plants(image_path, model, class_names, top_n=3, threshold=0.2):
    # 1. Load and Preprocess the image
    img = tf.keras.utils.load_img(image_path, target_size=(224, 224))
    img_array = tf.keras.utils.img_to_array(img)
    img_array = tf.expand_dims(img_array, 0)

    # 2. Predict
    predictions = model.predict(img_array)[0]

    # 3. Get the indices of the highest confidence scores
    top_indices = np.argsort(predictions)[-top_n:][::-1]

    print(f"--- Results for {image_path} ---")
    for i in top_indices:
        score = predictions[i]
        if score > threshold:
            print(f"Plant: {class_names[i]} | Confidence: {score:.2%}")
        else:
            print(f"(Low confidence) Potential: {class_names[i]} | {score:.2%}")

identify_plants('my_garden_photo.jpg', model, class_names)