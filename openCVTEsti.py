import cv2
import numpy as np

frame = np.zeros((400, 600, 3), dtype=np.uint8)
cv2.putText(frame, "TESTI", (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 3, (255,255,255), 3)

cv2.imshow("TESTI", frame)
cv2.waitKey(0)
cv2.destroyAllWindows()
