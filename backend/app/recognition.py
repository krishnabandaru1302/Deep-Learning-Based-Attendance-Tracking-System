from functools import lru_cache
from .settings import WEIGHTS_PATH


@lru_cache(maxsize=1)
def _descriptor_model():
    if not WEIGHTS_PATH.is_file():
        raise RuntimeError(f"VGGFace weights not found at {WEIGHTS_PATH}. See the setup guide.")
    try:
        from tensorflow.keras.models import Model, Sequential
        from tensorflow.keras.layers import (ZeroPadding2D, Convolution2D, MaxPooling2D,
                                             Flatten, Dropout, Activation)
    except ImportError as exc:
        raise RuntimeError("TensorFlow is not installed. Install backend/requirements.txt.") from exc
    m = Sequential(name="vggface_vgg16")
    m.add(ZeroPadding2D((1, 1), input_shape=(224, 224, 3)))
    for block, (filters, count) in enumerate(((64, 2), (128, 2), (256, 3), (512, 3), (512, 3))):
        for layer in range(count):
            # The input padding above is the first convolution's padding.
            if block > 0 or layer > 0:
                m.add(ZeroPadding2D((1, 1)))
            m.add(Convolution2D(filters, (3, 3), activation="relu"))
        m.add(MaxPooling2D((2, 2), strides=(2, 2)))
    m.add(Convolution2D(4096, (7, 7), activation="relu"))
    m.add(Dropout(0.5))
    m.add(Convolution2D(4096, (1, 1), activation="relu"))
    m.add(Dropout(0.5))
    m.add(Convolution2D(2622, (1, 1)))
    m.add(Flatten())
    m.add(Activation("softmax"))
    m.load_weights(str(WEIGHTS_PATH))
    return Model(inputs=m.layers[0].input, outputs=m.layers[-2].output)


def _decode(image_bytes):
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("OpenCV and NumPy are not installed. Install backend/requirements.txt.") from exc
    data = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Upload a valid JPEG or PNG image.")
    return image


def face_embedding(image_bytes):
    try:
        import cv2
        import numpy as np
        from tensorflow.keras.preprocessing.image import img_to_array
        from tensorflow.keras.applications.imagenet_utils import preprocess_input
    except ImportError as exc:
        raise RuntimeError("Recognition dependencies are not installed. Follow the setup guide.") from exc
    image = _decode(image_bytes)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    faces = detector.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5, minSize=(48, 48))
    if len(faces) != 1:
        raise ValueError(f"Expected exactly one detectable face; found {len(faces)}.")
    x, y, w, h = faces[0]
    crop = image[y:y+h, x:x+w]
    crop = cv2.resize(crop, (224, 224), interpolation=cv2.INTER_CUBIC)
    batch = np.expand_dims(img_to_array(crop), axis=0)
    vector = _descriptor_model().predict(preprocess_input(batch), verbose=0)[0]
    return vector.astype(float).tolist()


def cosine_distance(left, right):
    import numpy as np
    a, b = np.asarray(left, dtype=float), np.asarray(right, dtype=float)
    denominator = np.linalg.norm(a) * np.linalg.norm(b)
    if denominator == 0:
        return 1.0
    return float(1 - np.dot(a, b) / denominator)
