"""
YOLOv11 Fitness Trainer Model
Handles pose detection, exercise counting, and form analysis using YOLOv11 (Ultralytics)
"""

import cv2
import numpy as np
import time
from typing import List, Tuple, Dict, Optional
import os

try:
    from ultralytics import YOLO
    ULTRALYTICS_AVAILABLE = True
except ImportError:
    ULTRALYTICS_AVAILABLE = False
    print("⚠️ Ultralytics not available. Install with: pip install ultralytics")

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    print("⚠️ PyTorch not available. Install with: pip install torch torchvision")

class YOLOFitnessTrainer:
    """
    YOLOv11 based fitness trainer for pose detection and exercise counting
    """
    
    def __init__(
        self,
        model_path: Optional[str] = None,
        confidence_threshold: float = 0.5,
        debug: bool = False,
        imgsz: int = 640,
    ):
        """
        Initialize YOLOv11 pose model for pose detection
        
        Args:
            model_path: Path to YOLOv11 pose weights file (if None, will use yolo11n-pose.pt)
            confidence_threshold: Minimum confidence for detections
            debug: Enable debug output
        """
        self.confidence_threshold = confidence_threshold
        self.model = None
        self.device = 'cuda' if TORCH_AVAILABLE and torch.cuda.is_available() else 'cpu'
        # Inference image size (smaller is faster). 640 is a good default for pose.
        self.imgsz = imgsz
        self.model_path = model_path
        self.debug = debug
        
        # Exercise state tracking with improved validation
        self.exercise_state = {
            'pushups': {
                'count': 0, 
                'correct_count': 0,
                'incorrect_count': 0,
                'down_position': False, 
                'up_position': True,
                'prev_angle': 180,
                'min_angle_reached': 180,
                'form_quality': 'good',
                'last_rep_time': None
            },
            'squats': {
                'count': 0,
                'correct_count': 0,
                'incorrect_count': 0,
                'down_position': False,
                'up_position': True,
                'prev_angle': 180,
                'min_angle_reached': 180,
                'form_quality': 'good',
                'last_rep_time': None
            },
            'plank': {
                'count': 0,
                'start_time': None,
                'form_quality': 'good',
                'correct_count': 0,
                'incorrect_count': 0
            },
            'jumping_jacks': {
                'count': 0,
                'correct_count': 0,
                'incorrect_count': 0,
                'arms_up': False,
                'legs_spread': False,
                'prev_arm_distance': 0,
                'prev_leg_distance': 0,
                'form_quality': 'good',
                'last_rep_time': None
            },
            'burpees': {
                'count': 0,
                'correct_count': 0,
                'incorrect_count': 0,
                'phase': 'stand',
                'squat_depth': 180,
                'pushup_depth': 180,
                'form_quality': 'good',
                'last_rep_time': None
            }
        }
        
        # Minimum keypoints required for whole body detection
        self.required_keypoints = {
            'pushups': ['left_shoulder', 'right_shoulder', 'left_elbow', 'right_elbow', 
                       'left_wrist', 'right_wrist', 'left_hip', 'right_hip'],
            'squats': ['left_hip', 'right_hip', 'left_knee', 'right_knee', 
                      'left_ankle', 'right_ankle', 'left_shoulder', 'right_shoulder'],
            'plank': ['left_shoulder', 'right_shoulder', 'left_hip', 'right_hip',
                     'left_knee', 'right_knee', 'left_ankle', 'right_ankle'],
            'jumping_jacks': ['left_shoulder', 'right_shoulder', 'left_wrist', 'right_wrist',
                            'left_hip', 'right_hip', 'left_knee', 'right_knee'],
            'burpees': ['left_shoulder', 'right_shoulder', 'left_hip', 'right_hip',
                       'left_knee', 'right_knee', 'left_ankle', 'right_ankle']
        }
        
        # Keypoint indices for pose estimation (COCO format)
        self.keypoint_indices = {
            'nose': 0,
            'left_shoulder': 5, 'right_shoulder': 6,
            'left_elbow': 7, 'right_elbow': 8,
            'left_wrist': 9, 'right_wrist': 10,
            'left_hip': 11, 'right_hip': 12,
            'left_knee': 13, 'right_knee': 14,
            'left_ankle': 15, 'right_ankle': 16
        }
        
        if ULTRALYTICS_AVAILABLE:
            self._load_model()
        else:
            print("❌ Ultralytics is required. Install with: pip install ultralytics")
            self.model = None
    
    def _load_model(self):
        """Load YOLOv11 pose model"""
        try:
            if self.model_path and os.path.exists(self.model_path):
                # Load from local path
                print(f"📦 Loading YOLOv11 model from: {self.model_path}")
                self.model = YOLO(self.model_path)
            else:
                # Try different YOLOv11 pose models in order of preference
                # yolo11n-pose = nano (fastest, smallest)
                # yolo11s-pose = small (balanced)
                # yolo11m-pose = medium (better accuracy)
                # yolo11l-pose = large (high accuracy)
                # yolo11x-pose = extra large (best accuracy)
                pose_models = [
                    'yolo11n-pose.pt',  # Nano - fastest, good for real-time
                    'yolo11s-pose.pt',  # Small - balanced
                    'yolo11m-pose.pt', # Medium - better accuracy
                ]
                
                model_loaded = False
                for model_name in pose_models:
                    try:
                        print(f"📦 Attempting to load: {model_name}")
                        self.model = YOLO(model_name)  # Will auto-download if not present
                        model_loaded = True
                        print(f"✅ Successfully loaded: {model_name}")
                        break
                    except Exception as e:
                        print(f"⚠️ Failed to load {model_name}: {e}")
                        continue
                
                if not model_loaded:
                    raise Exception("Could not load any YOLOv11 pose model")
            
            # Move model to the desired device explicitly (extra safety)
            try:
                if TORCH_AVAILABLE and hasattr(self.model, "to"):
                    self.model.to(self.device)
            except Exception:
                # If this fails, Ultralytics will still handle device internally
                pass

            print(f"✅ YOLOv11 pose model loaded successfully")
            print(f"📊 Device: {self.device}")
            print(f"📊 Confidence threshold: {self.confidence_threshold}")
            
        except Exception as e:
            print(f"❌ Error loading YOLOv11 pose model: {e}")
            print("💡 Make sure you have internet connection for first-time download")
            print("💡 Install ultralytics: pip install ultralytics")
            import traceback
            traceback.print_exc()
            self.model = None
    
    def detect_pose(self, frame: np.ndarray) -> Dict:
        """
        Detect human pose in frame using YOLOv11
        
        Args:
            frame: Input image frame (BGR format)
            
        Returns:
            Dictionary with detection results including keypoints
        """
        if not ULTRALYTICS_AVAILABLE or self.model is None:
            return {'detected': False, 'keypoints': None, 'bbox': None}
        
        try:
            # Ultralytics YOLO accepts BGR frames directly, but RGB is preferred
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Run inference with confidence threshold
            results = self.model.predict(
                rgb_frame,
                conf=self.confidence_threshold,
                imgsz=self.imgsz,
                verbose=False,
                device=self.device,
            )
            
            # Extract pose keypoints
            # Ultralytics YOLOv11 returns results as a list of Results objects
            keypoints = None
            bbox = None
            detected = False
            
            try:
                # Get first result (Ultralytics returns list)
                if len(results) > 0:
                    result = results[0]
                    
                    # Extract keypoints from Ultralytics Results object
                    if hasattr(result, 'keypoints') and result.keypoints is not None:
                        # Ultralytics keypoints format: keypoints.data is tensor [num_persons, num_keypoints, 3]
                        kp_data = result.keypoints.data
                        
                        # Convert tensor to numpy
                        if hasattr(kp_data, 'cpu'):
                            kp_data = kp_data.cpu().numpy()
                        else:
                            kp_data = np.array(kp_data)
                        
                        # Handle keypoint shapes
                        # Shape: [num_persons, num_keypoints, 3] where 3 = [x, y, confidence]
                        if len(kp_data.shape) == 3:  # [persons, keypoints, 3]
                            if kp_data.shape[0] > 0:  # At least one person detected
                                # Get first person's keypoints
                                keypoints = kp_data[0]  # Shape: [num_keypoints, 3]
                        elif len(kp_data.shape) == 2:  # [keypoints, 3] - single person
                            keypoints = kp_data
                        
                        # Validate keypoints
                        if keypoints is not None and len(keypoints.shape) == 2:
                            if keypoints.shape[0] > 0 and keypoints.shape[1] >= 2:
                                detected = True
                                if self.debug:
                                    valid_kps = sum(1 for kp in keypoints if len(kp) >= 3 and kp[2] > 0.05)
                                    print(f"🔍 Detected {keypoints.shape[0]} keypoints, {valid_kps} with confidence > 0.05")
                    
                    # Extract bounding box
                    if detected and hasattr(result, 'boxes') and result.boxes is not None:
                        boxes = result.boxes
                        if hasattr(boxes, 'xyxy') and len(boxes.xyxy) > 0:
                            # Get first person's bounding box
                            bbox_tensor = boxes.xyxy[0]
                            if hasattr(bbox_tensor, 'cpu'):
                                bbox = bbox_tensor.cpu().numpy()
                            else:
                                bbox = np.array(bbox_tensor)
                    
            except Exception as e:
                if self.debug:
                    print(f"⚠️ Error processing keypoints: {e}")
                    import traceback
                    traceback.print_exc()
                keypoints = None
            
            return {
                'detected': detected,
                'keypoints': keypoints,
                'bbox': bbox,
                'raw_results': results
            }
        except Exception as e:
            print(f"❌ Error in pose detection: {e}")
            import traceback
            traceback.print_exc()
            return {'detected': False, 'keypoints': None, 'bbox': None}
    
    def calculate_angle(self, point1: np.ndarray, point2: np.ndarray, point3: np.ndarray) -> float:
        """
        Calculate angle between three points
        
        Args:
            point1, point2, point3: Points forming the angle (point2 is vertex)
            
        Returns:
            Angle in degrees
        """
        try:
            a = point1 - point2
            b = point3 - point2
            cos_angle = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-6)
            cos_angle = np.clip(cos_angle, -1.0, 1.0)
            angle = np.arccos(cos_angle) * 180 / np.pi
            return angle
        except:
            return 180.0
    
    def get_keypoint(self, keypoints: np.ndarray, keypoint_name: str) -> Optional[np.ndarray]:
        """Get specific keypoint from keypoints array with improved validation"""
        if keypoints is None:
            return None
        try:
            idx = self.keypoint_indices.get(keypoint_name)
            if idx is not None and idx < len(keypoints):
                kp = keypoints[idx]
                # Handle different keypoint formats: [x, y] or [x, y, confidence]
                if len(kp) >= 2:
                    # Improved confidence check - require minimum 0.15 confidence for better accuracy
                    if len(kp) >= 3:
                        # Reject if confidence is too low or coordinates are invalid
                        if kp[2] < 0.15:
                            return None
                        # Check if coordinates are valid (positive values)
                        if kp[0] <= 0 or kp[1] <= 0:
                            return None
                    else:
                        # No confidence value, just check coordinates
                        if kp[0] <= 0 or kp[1] <= 0:
                            return None
                    return kp[:2]  # Return x, y coordinates
        except Exception as e:
            # Silently fail for individual keypoints to avoid spam
            pass
        return None
    
    def validate_whole_body(self, keypoints: np.ndarray, exercise_type: str) -> bool:
        """Validate that enough keypoints are detected for whole body tracking"""
        if keypoints is None:
            return False
        
        exercise_type_lower = exercise_type.lower().replace('-', '_').replace(' ', '_')
        
        # Handle exercise name variations to match required_keypoints keys
        exercise_key_map = {
            'push_ups': 'pushups',
            'pushups': 'pushups',
            'jumping_jacks': 'jumping_jacks',
            'jumpingjacks': 'jumping_jacks',
            'squats': 'squats',
            'plank': 'plank',
            'burpees': 'burpees'
        }
        
        # Get the canonical exercise name
        canonical_name = exercise_key_map.get(exercise_type_lower, exercise_type_lower)
        required = self.required_keypoints.get(canonical_name, [])
        
        if not required:
            return True  # No requirements, allow
        
        # Check if all required keypoints are detected
        detected_count = 0
        for kp_name in required:
            if self.get_keypoint(keypoints, kp_name) is not None:
                detected_count += 1
        
        # Require at least 75% of keypoints to be detected
        min_required = int(len(required) * 0.75)
        return detected_count >= min_required
    
    def detect_pushup(self, keypoints: np.ndarray) -> Tuple[bool, int, Dict]:
        """
        Detect push-up rep completion with form validation
        
        Returns:
            (rep_completed, current_count, form_info)
        """
        if keypoints is None:
            state = self.exercise_state['pushups']
            return False, state['count'], {
                'form_quality': 'poor', 
                'reason': 'No pose detected',
                'correct_count': state.get('correct_count', 0),
                'incorrect_count': state.get('incorrect_count', 0)
            }
        
        # Get key points
        left_shoulder = self.get_keypoint(keypoints, 'left_shoulder')
        right_shoulder = self.get_keypoint(keypoints, 'right_shoulder')
        left_elbow = self.get_keypoint(keypoints, 'left_elbow')
        right_elbow = self.get_keypoint(keypoints, 'right_elbow')
        left_wrist = self.get_keypoint(keypoints, 'left_wrist')
        right_wrist = self.get_keypoint(keypoints, 'right_wrist')
        left_hip = self.get_keypoint(keypoints, 'left_hip')
        right_hip = self.get_keypoint(keypoints, 'right_hip')
        
        # Require essential keypoints
        if not all([left_shoulder is not None, right_shoulder is not None,
                   left_elbow is not None, right_elbow is not None]):
            state = self.exercise_state['pushups']
            return False, state['count'], {
                'form_quality': 'poor', 
                'reason': 'Missing keypoints',
                'correct_count': state.get('correct_count', 0),
                'incorrect_count': state.get('incorrect_count', 0)
            }
        
        # Check body alignment (shoulders and hips should be relatively aligned)
        form_quality = 'good'
        form_reason = ''
        
        if left_hip is not None and right_hip is not None:
            shoulder_avg_y = (left_shoulder[1] + right_shoulder[1]) / 2
            hip_avg_y = (left_hip[1] + right_hip[1]) / 2
            # Body should be relatively straight (not sagging)
            body_alignment = abs(shoulder_avg_y - hip_avg_y)
            if body_alignment > 80:  # Too much sagging
                form_quality = 'poor'
                form_reason = 'Body not straight - keep core engaged'
        
        # Calculate average elbow angle
        angle1 = self.calculate_angle(left_shoulder, left_elbow, left_wrist) if left_wrist is not None else 180
        angle2 = self.calculate_angle(right_shoulder, right_elbow, right_wrist) if right_wrist is not None else 180
        avg_angle = (angle1 + angle2) / 2
        
        state = self.exercise_state['pushups']
        rep_completed = False
        is_correct_rep = False
        
        # Track minimum angle reached (for full range of motion validation)
        if avg_angle < state['min_angle_reached']:
            state['min_angle_reached'] = avg_angle
        
        # Detect down position - require angle < 85 for proper depth
        if avg_angle < 85 and not state['down_position']:
            state['down_position'] = True
            state['up_position'] = False
        
        # Detect up position - require angle > 165 for full extension
        if avg_angle > 165 and state['down_position']:
            # Validate full range of motion
            if state['min_angle_reached'] < 80:  # Went deep enough
                is_correct_rep = True
                state['correct_count'] += 1
            else:
                form_quality = 'poor'
                form_reason = 'Incomplete range of motion - go deeper'
                state['incorrect_count'] += 1
            
            state['down_position'] = False
            state['up_position'] = True
            state['count'] += 1
            state['min_angle_reached'] = 180  # Reset for next rep
            rep_completed = True
            state['last_rep_time'] = time.time()
        
        # Update form quality
        state['form_quality'] = form_quality
        
        # Always return current counts (even if no rep completed)
        form_info = {
            'form_quality': form_quality,
            'reason': form_reason,
            'angle': avg_angle,
            'is_correct': is_correct_rep,
            'correct_count': state.get('correct_count', 0),
            'incorrect_count': state.get('incorrect_count', 0)
        }
        
        state['prev_angle'] = avg_angle
        return rep_completed, state['count'], form_info
    
    def detect_squat(self, keypoints: np.ndarray) -> Tuple[bool, int, Dict]:
        """
        Detect squat rep completion with form validation
        
        Returns:
            (rep_completed, current_count, form_info)
        """
        if keypoints is None:
            state = self.exercise_state['squats']
            return False, state['count'], {
                'form_quality': 'poor', 
                'reason': 'No pose detected',
                'correct_count': state.get('correct_count', 0),
                'incorrect_count': state.get('incorrect_count', 0)
            }
        
        # Get key points
        left_hip = self.get_keypoint(keypoints, 'left_hip')
        right_hip = self.get_keypoint(keypoints, 'right_hip')
        left_knee = self.get_keypoint(keypoints, 'left_knee')
        right_knee = self.get_keypoint(keypoints, 'right_knee')
        left_ankle = self.get_keypoint(keypoints, 'left_ankle')
        right_ankle = self.get_keypoint(keypoints, 'right_ankle')
        left_shoulder = self.get_keypoint(keypoints, 'left_shoulder')
        right_shoulder = self.get_keypoint(keypoints, 'right_shoulder')
        
        if not all([left_hip is not None, right_hip is not None,
                   left_knee is not None, right_knee is not None]):
            state = self.exercise_state['squats']
            return False, state['count'], {
                'form_quality': 'poor', 
                'reason': 'Missing keypoints',
                'correct_count': state.get('correct_count', 0),
                'incorrect_count': state.get('incorrect_count', 0)
            }
        
        # Form validation
        form_quality = 'good'
        form_reason = ''
        
        # Check knee alignment (knees should track over toes, not cave inward)
        if left_ankle is not None and right_ankle is not None:
            knee_ankle_left = abs(left_knee[0] - left_ankle[0])
            knee_ankle_right = abs(right_knee[0] - right_ankle[0])
            # If knees are too far from ankles, form is poor (more lenient threshold)
            if knee_ankle_left > 80 or knee_ankle_right > 80:
                form_quality = 'poor'
                form_reason = 'Knees caving in - keep them over toes'
        
        # Check back alignment (shoulders should stay relatively upright)
        if left_shoulder is not None and right_shoulder is not None:
            shoulder_avg_y = (left_shoulder[1] + right_shoulder[1]) / 2
            hip_avg_y = (left_hip[1] + right_hip[1]) / 2
            # Calculate forward lean (more lenient threshold)
            if shoulder_avg_y > hip_avg_y + 150:  # Too much forward lean
                form_quality = 'poor'
                form_reason = 'Keep chest up and back straight'
        
        # Calculate average knee angle
        angle1 = self.calculate_angle(left_hip, left_knee, left_ankle) if left_ankle is not None else 180
        angle2 = self.calculate_angle(right_hip, right_knee, right_ankle) if right_ankle is not None else 180
        avg_angle = (angle1 + angle2) / 2
        
        state = self.exercise_state['squats']
        rep_completed = False
        is_correct_rep = False
        
        # Track minimum angle reached
        if avg_angle < state['min_angle_reached']:
            state['min_angle_reached'] = avg_angle
        
        # Detect down position - require angle < 110 for proper depth (more lenient)
        if avg_angle < 110 and not state['down_position']:
            state['down_position'] = True
            state['up_position'] = False
        
        # Detect up position - require angle > 150 for full extension (more lenient)
        if avg_angle > 150 and state['down_position']:
            # Validate full range of motion - check if went deep enough
            min_depth = state.get('min_angle_reached', 180)
            if min_depth < 100:  # Went deep enough (more lenient threshold)
                is_correct_rep = True
                state['correct_count'] += 1
            else:
                form_quality = 'poor'
                form_reason = 'Incomplete range of motion - go deeper'
                state['incorrect_count'] += 1
            
            state['down_position'] = False
            state['up_position'] = True
            state['count'] += 1
            state['min_angle_reached'] = 180  # Reset for next rep
            rep_completed = True
            state['last_rep_time'] = time.time()
        
        # Update form quality
        state['form_quality'] = form_quality
        
        # Always return current counts (even if no rep completed)
        form_info = {
            'form_quality': form_quality,
            'reason': form_reason,
            'angle': avg_angle,
            'is_correct': is_correct_rep,
            'correct_count': state.get('correct_count', 0),
            'incorrect_count': state.get('incorrect_count', 0)
        }
        
        state['prev_angle'] = avg_angle
        return rep_completed, state['count'], form_info
    
    def detect_plank(self, keypoints: np.ndarray) -> Tuple[bool, int, Dict]:
        """
        Detect plank hold duration with form validation
        
        Returns:
            (is_holding, current_count, form_info)
        """
        if keypoints is None:
            state = self.exercise_state['plank']
            return False, state['count'], {
                'form_quality': 'poor',
                'reason': 'No pose detected',
                'duration': 0.0,
                'correct_count': 0,
                'incorrect_count': 0
            }
        
        # Get key points for alignment check
        left_shoulder = self.get_keypoint(keypoints, 'left_shoulder')
        right_shoulder = self.get_keypoint(keypoints, 'right_shoulder')
        left_hip = self.get_keypoint(keypoints, 'left_hip')
        right_hip = self.get_keypoint(keypoints, 'right_hip')
        left_ankle = self.get_keypoint(keypoints, 'left_ankle')
        right_ankle = self.get_keypoint(keypoints, 'right_ankle')
        
        if not all([left_shoulder is not None, right_shoulder is not None, 
                   left_hip is not None, right_hip is not None]):
            state = self.exercise_state['plank']
            return False, state['count'], {
                'form_quality': 'poor',
                'reason': 'Missing keypoints',
                'duration': 0.0,
                'correct_count': 0,
                'incorrect_count': 0
            }
        
        # Check if body is relatively straight (plank position)
        shoulder_avg_y = (left_shoulder[1] + right_shoulder[1]) / 2
        hip_avg_y = (left_hip[1] + right_hip[1]) / 2
        
        # More lenient tolerance for straight line
        alignment_threshold = 80  # pixels (increased from 50)
        alignment_diff = abs(shoulder_avg_y - hip_avg_y)
        is_aligned = alignment_diff < alignment_threshold
        
        state = self.exercise_state['plank']
        form_quality = 'good'
        form_reason = ''
        
        # Form validation - check if hips are too high or too low
        if not is_aligned:
            if hip_avg_y < shoulder_avg_y - 30:  # Hips too high
                form_quality = 'poor'
                form_reason = 'Hips too high - lower them'
            elif hip_avg_y > shoulder_avg_y + alignment_threshold:  # Hips sagging
                form_quality = 'poor'
                form_reason = 'Hips sagging - keep body straight'
        
        if is_aligned:
            if state['start_time'] is None:
                state['start_time'] = time.time()
            
            duration = time.time() - state['start_time']
            # Count every 3 seconds as a "rep" (more frequent counting)
            new_count = int(duration / 3)
            if new_count > state['count']:
                state['count'] = new_count
                # Mark as correct if form is good
                if form_quality == 'good':
                    state['correct_count'] = state.get('correct_count', 0) + 1
                else:
                    state['incorrect_count'] = state.get('incorrect_count', 0) + 1
            
            state['form_quality'] = form_quality
            
            return True, state['count'], {
                'form_quality': form_quality,
                'reason': form_reason,
                'duration': duration,
                'correct_count': state.get('correct_count', 0),
                'incorrect_count': state.get('incorrect_count', 0)
            }
        else:
            # Reset if alignment is lost
            if state['start_time'] is not None:
                state['start_time'] = None
            
            return False, state['count'], {
                'form_quality': form_quality,
                'reason': form_reason if form_reason else 'Not in plank position',
                'duration': 0.0,
                'correct_count': state.get('correct_count', 0),
                'incorrect_count': state.get('incorrect_count', 0)
            }
    
    def detect_jumping_jack(self, keypoints: np.ndarray) -> Tuple[bool, int, Dict]:
        """
        Detect jumping jack rep completion with form validation
        
        Returns:
            (rep_completed, current_count, form_info)
        """
        if keypoints is None:
            state = self.exercise_state['jumping_jacks']
            return False, state['count'], {
                'form_quality': 'poor', 
                'reason': 'No pose detected',
                'correct_count': state.get('correct_count', 0),
                'incorrect_count': state.get('incorrect_count', 0)
            }
        
        # Get key points
        left_shoulder = self.get_keypoint(keypoints, 'left_shoulder')
        right_shoulder = self.get_keypoint(keypoints, 'right_shoulder')
        left_wrist = self.get_keypoint(keypoints, 'left_wrist')
        right_wrist = self.get_keypoint(keypoints, 'right_wrist')
        left_hip = self.get_keypoint(keypoints, 'left_hip')
        right_hip = self.get_keypoint(keypoints, 'right_hip')
        left_knee = self.get_keypoint(keypoints, 'left_knee')
        right_knee = self.get_keypoint(keypoints, 'right_knee')
        
        if not all([left_shoulder is not None, right_shoulder is not None, 
                   left_wrist is not None, right_wrist is not None]):
            state = self.exercise_state['jumping_jacks']
            return False, state['count'], {
                'form_quality': 'poor', 
                'reason': 'Missing keypoints',
                'correct_count': state.get('correct_count', 0),
                'incorrect_count': state.get('incorrect_count', 0)
            }
        
        # Calculate distances
        arm_distance = np.linalg.norm(left_wrist - right_wrist)
        leg_distance = 0
        if left_knee is not None and right_knee is not None:
            leg_distance = np.linalg.norm(left_knee - right_knee)
        
        # Calculate arm height (should be overhead)
        arm_height = 0
        if left_wrist is not None and right_wrist is not None and left_shoulder is not None:
            wrist_avg_y = (left_wrist[1] + right_wrist[1]) / 2
            shoulder_avg_y = (left_shoulder[1] + right_shoulder[1]) / 2
            arm_height = shoulder_avg_y - wrist_avg_y  # Positive means wrists above shoulders
        
        state = self.exercise_state['jumping_jacks']
        rep_completed = False
        is_correct_rep = False
        form_quality = 'good'
        form_reason = ''
        
        # Arm spread threshold (should be wide)
        arm_threshold = 180  # pixels
        # Leg spread threshold
        leg_threshold = 100 if leg_distance > 0 else 0
        
        # Detect full extension (arms up AND legs spread)
        arms_extended = arm_distance > arm_threshold and arm_height > 30
        legs_extended = leg_distance > leg_threshold if leg_threshold > 0 else True
        
        if arms_extended and legs_extended and not state['arms_up']:
            state['arms_up'] = True
            state['legs_spread'] = True
        
        # Detect return to start (arms down AND legs together)
        arms_down = arm_distance < arm_threshold * 0.7
        legs_together = leg_distance < leg_threshold * 0.7 if leg_threshold > 0 else True
        
        if (arms_down and legs_together) and state['arms_up']:
            # Validate full extension was achieved
            if state['prev_arm_distance'] > arm_threshold:
                is_correct_rep = True
                state['correct_count'] += 1
            else:
                form_quality = 'poor'
                form_reason = 'Incomplete extension - fully extend arms and legs'
                state['incorrect_count'] += 1
            
            state['arms_up'] = False
            state['legs_spread'] = False
            state['count'] += 1
            rep_completed = True
            state['last_rep_time'] = time.time()
        
        state['prev_arm_distance'] = arm_distance
        state['prev_leg_distance'] = leg_distance
        state['form_quality'] = form_quality
        
        # Always return current counts (even if no rep completed)
        form_info = {
            'form_quality': form_quality,
            'reason': form_reason,
            'is_correct': is_correct_rep,
            'correct_count': state.get('correct_count', 0),
            'incorrect_count': state.get('incorrect_count', 0)
        }
        
        return rep_completed, state['count'], form_info
    
    def detect_burpee(self, keypoints: np.ndarray) -> Tuple[bool, int, Dict]:
        """
        Detect burpee rep completion with form validation
        Simplified: Uses squat detection as burpees include a squat motion
        
        Returns:
            (rep_completed, current_count, form_info)
        """
        if keypoints is None:
            state = self.exercise_state['burpees']
            return False, state['count'], {
                'form_quality': 'poor', 
                'reason': 'No pose detected',
                'correct_count': state.get('correct_count', 0),
                'incorrect_count': state.get('incorrect_count', 0)
            }
        
        # Use squat detection logic for burpees (burpees include squat motion)
        # This is more reliable than the complex state machine
        try:
            rep_completed, count, form_info = self.detect_squat(keypoints)
            
            # Update burpee-specific state
            state = self.exercise_state['burpees']
            
            # Only update burpee count if squat detected a rep
            if rep_completed:
                # Check if this is a new rep (prevent double counting)
                current_time = time.time()
                last_rep_time = state.get('last_rep_time', 0)
                
                # Only count if at least 1 second has passed since last rep
                if current_time - last_rep_time > 1.0:
                    state['count'] = count
                    state['last_rep_time'] = current_time
                    
                    # Update correct/incorrect counts based on form
                    if form_info.get('is_correct', False):
                        state['correct_count'] = state.get('correct_count', 0) + 1
                    else:
                        state['incorrect_count'] = state.get('incorrect_count', 0) + 1
                else:
                    # Too soon, don't count as new rep
                    rep_completed = False
            
            # Return burpee-specific counts
            form_info['correct_count'] = state.get('correct_count', 0)
            form_info['incorrect_count'] = state.get('incorrect_count', 0)
            form_info['reason'] = form_info.get('reason', '')
            
            return rep_completed, state['count'], form_info
            
        except Exception as e:
            # Error handling to prevent crashes
            state = self.exercise_state['burpees']
            return False, state.get('count', 0), {
                'form_quality': 'poor',
                'reason': f'Detection error: {str(e)}',
                'correct_count': state.get('correct_count', 0),
                'incorrect_count': state.get('incorrect_count', 0)
            }
    
    def count_exercise(self, keypoints: np.ndarray, exercise_type: str) -> Tuple[bool, int, Dict]:
        """
        Count reps for specified exercise type with whole body validation
        
        Args:
            keypoints: Detected pose keypoints
            exercise_type: Type of exercise ('Push-ups', 'Squats', 'Plank', 'Jumping Jacks', 'Burpees')
            
        Returns:
            (rep_completed, current_count, additional_info)
        """
        try:
            # First validate whole body is detected
            if not self.validate_whole_body(keypoints, exercise_type):
                exercise_type_lower = exercise_type.lower().replace('-', '_').replace(' ', '_')
                # Handle exercise name variations
                exercise_key_map = {
                    'push_ups': 'pushups',
                    'pushups': 'pushups',
                    'jumping_jacks': 'jumping_jacks',
                    'jumpingjacks': 'jumping_jacks',
                    'squats': 'squats',
                    'plank': 'plank',
                    'burpees': 'burpees'
                }
                canonical_name = exercise_key_map.get(exercise_type_lower, exercise_type_lower)
                state = self.exercise_state.get(canonical_name, {})
                return False, state.get('count', 0), {
                    'form_quality': 'poor', 
                    'reason': 'Whole body not detected - move into camera view',
                    'correct_count': state.get('correct_count', 0),
                    'incorrect_count': state.get('incorrect_count', 0)
                }
            
            exercise_type_lower = exercise_type.lower().replace('-', '_').replace(' ', '_')
            
            if exercise_type_lower == 'push_ups' or exercise_type_lower == 'pushups':
                rep_completed, count, form_info = self.detect_pushup(keypoints)
                return rep_completed, count, form_info
            elif exercise_type_lower == 'squats':
                rep_completed, count, form_info = self.detect_squat(keypoints)
                return rep_completed, count, form_info
            elif exercise_type_lower == 'plank':
                is_holding, count, form_info = self.detect_plank(keypoints)
                return is_holding, count, form_info
            elif exercise_type_lower == 'jumping_jacks':
                rep_completed, count, form_info = self.detect_jumping_jack(keypoints)
                return rep_completed, count, form_info
            elif exercise_type_lower == 'burpees':
                # Use proper burpee detection
                rep_completed, count, form_info = self.detect_burpee(keypoints)
                return rep_completed, count, form_info
            else:
                return False, 0, {'form_quality': 'poor', 'reason': 'Unknown exercise type'}
                
        except Exception as e:
            # Error handling to prevent crashes
            exercise_type_lower = exercise_type.lower().replace('-', '_').replace(' ', '_')
            exercise_key_map = {
                'push_ups': 'pushups',
                'pushups': 'pushups',
                'jumping_jacks': 'jumping_jacks',
                'jumpingjacks': 'jumping_jacks',
                'squats': 'squats',
                'plank': 'plank',
                'burpees': 'burpees'
            }
            canonical_name = exercise_key_map.get(exercise_type_lower, exercise_type_lower)
            state = self.exercise_state.get(canonical_name, {})
            return False, state.get('count', 0), {
                'form_quality': 'poor',
                'reason': f'Error: {str(e)}',
                'correct_count': state.get('correct_count', 0),
                'incorrect_count': state.get('incorrect_count', 0)
            }
    
    def reset_exercise(self, exercise_type: str):
        """Reset counter for specific exercise"""
        exercise_type_lower = exercise_type.lower().replace('-', '_').replace(' ', '_')
        
        # Reset state based on exercise type
        if exercise_type_lower == 'pushups' or exercise_type_lower == 'push_ups':
            self.exercise_state['pushups'] = {
                'count': 0, 
                'correct_count': 0,
                'incorrect_count': 0,
                'down_position': False, 
                'up_position': True,
                'prev_angle': 180,
                'min_angle_reached': 180,
                'form_quality': 'good',
                'last_rep_time': None
            }
        elif exercise_type_lower == 'squats':
            self.exercise_state['squats'] = {
                'count': 0,
                'correct_count': 0,
                'incorrect_count': 0,
                'down_position': False,
                'up_position': True,
                'prev_angle': 180,
                'min_angle_reached': 180,
                'form_quality': 'good',
                'last_rep_time': None
            }
        elif exercise_type_lower == 'plank':
            self.exercise_state['plank'] = {
                'count': 0,
                'start_time': None,
                'form_quality': 'good',
                'correct_count': 0,
                'incorrect_count': 0
            }
        elif exercise_type_lower == 'jumping_jacks':
            self.exercise_state['jumping_jacks'] = {
                'count': 0,
                'correct_count': 0,
                'incorrect_count': 0,
                'arms_up': False,
                'legs_spread': False,
                'prev_arm_distance': 0,
                'prev_leg_distance': 0,
                'form_quality': 'good',
                'last_rep_time': None
            }
        elif exercise_type_lower == 'burpees':
            self.exercise_state['burpees'] = {
                'count': 0,
                'correct_count': 0,
                'incorrect_count': 0,
                'phase': 'stand',
                'squat_depth': 180,
                'pushup_depth': 180,
                'form_quality': 'good',
                'last_rep_time': None
            }
    
    def draw_pose(self, frame: np.ndarray, keypoints: np.ndarray, bbox: Optional[np.ndarray] = None, form_quality: str = 'good') -> np.ndarray:
        """
        Draw pose keypoints and skeleton on frame
        
        Args:
            frame: Input frame
            keypoints: Detected keypoints
            bbox: Bounding box (optional)
            
        Returns:
            Frame with pose visualization
        """
        if keypoints is None:
            return frame
        
        frame_copy = frame.copy()
        
        # Draw bounding box if available with color based on form quality
        if bbox is not None:
            try:
                x1, y1, x2, y2 = map(int, bbox[:4])
                # Color based on form: green=good, yellow=fair, red=poor
                if form_quality == 'good':
                    box_color = (0, 255, 0)  # Green
                elif form_quality == 'fair':
                    box_color = (0, 255, 255)  # Yellow
                else:
                    box_color = (0, 0, 255)  # Red
                cv2.rectangle(frame_copy, (x1, y1), (x2, y2), box_color, 3)
            except:
                pass
        
        # Very low confidence threshold for better visualization - show all detected keypoints
        confidence_threshold = 0.05
        
        # Draw keypoints - show all detected keypoints
        for idx, kp in enumerate(keypoints):
            try:
                if len(kp) >= 2:
                    # Check confidence if available (3rd element)
                    confidence = kp[2] if len(kp) >= 3 else 1.0
                    x, y = int(kp[0]), int(kp[1])
                    # Draw if coordinates are valid and confidence is above threshold
                    if x > 0 and y > 0 and confidence >= confidence_threshold:
                        # Color based on confidence - brighter for higher confidence
                        color_intensity = int(255 * min(max(confidence, 0.3), 1.0))  # Minimum brightness
                        cv2.circle(frame_copy, (x, y), 7, (0, color_intensity, 0), -1)
                        cv2.circle(frame_copy, (x, y), 7, (255, 255, 255), 2)
                        # Draw keypoint index for debugging (optional)
                        # cv2.putText(frame_copy, str(idx), (x+10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255,255,255), 1)
            except:
                continue
        
        # Draw skeleton connections
        connections = [
            ('left_shoulder', 'right_shoulder'),
            ('left_shoulder', 'left_elbow'),
            ('left_elbow', 'left_wrist'),
            ('right_shoulder', 'right_elbow'),
            ('right_elbow', 'right_wrist'),
            ('left_shoulder', 'left_hip'),
            ('right_shoulder', 'right_hip'),
            ('left_hip', 'right_hip'),
            ('left_hip', 'left_knee'),
            ('left_knee', 'left_ankle'),
            ('right_hip', 'right_knee'),
            ('right_knee', 'right_ankle'),
        ]
        
        for start_name, end_name in connections:
            try:
                start_idx = self.keypoint_indices.get(start_name)
                end_idx = self.keypoint_indices.get(end_name)
                
                if start_idx is not None and end_idx is not None:
                    if start_idx < len(keypoints) and end_idx < len(keypoints):
                        start_kp = keypoints[start_idx]
                        end_kp = keypoints[end_idx]
                        
                        if len(start_kp) >= 2 and len(end_kp) >= 2:
                            start_conf = start_kp[2] if len(start_kp) > 2 else 1.0
                            end_conf = end_kp[2] if len(end_kp) > 2 else 1.0
                            
                            # Draw line if both keypoints have sufficient confidence and valid coordinates
                            x1, y1 = int(start_kp[0]), int(start_kp[1])
                            x2, y2 = int(end_kp[0]), int(end_kp[1])
                            
                            # Only draw if coordinates are valid
                            if x1 > 0 and y1 > 0 and x2 > 0 and y2 > 0:
                                if start_conf >= confidence_threshold and end_conf >= confidence_threshold:
                                    # Line color based on average confidence
                                    avg_conf = (start_conf + end_conf) / 2
                                    color_intensity = int(255 * min(max(avg_conf, 0.3), 1.0))  # Minimum brightness
                                    cv2.line(frame_copy, (x1, y1), (x2, y2), (color_intensity, 0, 0), 3)
            except:
                continue
        
        return frame_copy


# Main application entry point
if __name__ == "__main__":
    print("🚀 Starting YOLOv11 Fitness Trainer...")
    print("=" * 50)
    
    # Initialize the trainer with optimized settings
    trainer = YOLOFitnessTrainer(confidence_threshold=0.25, debug=False)
    
    if trainer.model is None:
        print("❌ Failed to load model. Exiting...")
        exit(1)
    
    # Open camera (0 for default camera)
    cap = cv2.VideoCapture(0)
    
    # Set camera properties – slightly lower resolution for smoother real‑time FPS
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 960)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 540)
    cap.set(cv2.CAP_PROP_FPS, 30)
    
    if not cap.isOpened():
        print("❌ Failed to open camera")
        print("💡 Make sure your camera is connected and not being used by another application")
        exit(1)
    
    print("✅ Camera opened successfully")
    print("📋 Controls:")
    print("   - Press 'Q' to quit")
    print("   - Press 'R' to reset exercise counters")
    print("   - Press '1' for Push-ups")
    print("   - Press '2' for Squats")
    print("   - Press '3' for Plank")
    print("   - Press '4' for Jumping Jacks")
    print("=" * 50)
    
    # Exercise tracking
    current_exercise = "Push-ups"
    exercise_names = {
        '1': 'Push-ups',
        '2': 'Squats',
        '3': 'Plank',
        '4': 'Jumping Jacks'
    }
    
    frame_count = 0
    fps_start_time = time.time()
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("⚠️ Failed to read from camera")
                break
            
            # Flip frame horizontally for mirror effect
            frame = cv2.flip(frame, 1)
            
            # Detect pose
            result = trainer.detect_pose(frame)
            keypoints = result['keypoints']
            bbox = result['bbox']
            detected = result['detected']
            
            # Draw pose visualization
            output_frame = trainer.draw_pose(frame, keypoints, bbox)
            
            # Count exercise if keypoints are detected
            exercise_info = {}
            if detected and keypoints is not None:
                rep_done, count, info = trainer.count_exercise(keypoints, current_exercise)
                exercise_info = {'count': count, 'rep_done': rep_done, **info}
                
                # Show rep completion feedback
                if rep_done:
                    # Flash green overlay
                    overlay = output_frame.copy()
                    cv2.rectangle(overlay, (0, 0), (output_frame.shape[1], output_frame.shape[0]), (0, 255, 0), -1)
                    cv2.addWeighted(overlay, 0.3, output_frame, 0.7, 0, output_frame)
            
            # Minimal on-screen information for the user
            cv2.putText(
                output_frame,
                f"Exercise: {current_exercise}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2,
            )

            if exercise_info:
                count = exercise_info.get("count", 0)
                cv2.putText(
                    output_frame,
                    f"Reps: {count}",
                    (10, 70),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.0,
                    (0, 255, 0),
                    2,
                )

                if "duration" in exercise_info:
                    duration = exercise_info["duration"]
                    cv2.putText(
                        output_frame,
                        f"Time: {duration:.1f}s",
                        (10, 110),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 255, 255),
                        2,
                    )
            
            # Display frame
            cv2.imshow("YOLO Fitness Trainer - Pose Detection", output_frame)
            
            # Handle keyboard input
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == ord('Q'):
                print("👋 Exiting...")
                break
            elif key == ord('r') or key == ord('R'):
                trainer.reset_exercise(current_exercise)
                print(f"🔄 Reset {current_exercise} counter")
            elif key in exercise_names:
                current_exercise = exercise_names[key]
                trainer.reset_exercise(current_exercise)
                print(f"📝 Switched to {current_exercise}")
    
    except KeyboardInterrupt:
        print("\n👋 Interrupted by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        cap.release()
        cv2.destroyAllWindows()
        print("✅ Camera released. Goodbye!")