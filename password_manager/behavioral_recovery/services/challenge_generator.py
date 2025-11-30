"""
Challenge Generator

Generates behavioral challenges for recovery
"""

import logging
import random
from ..models import BehavioralChallenge

logger = logging.getLogger(__name__)


class ChallengeGenerator:
    """
    Generates behavioral challenges for recovery attempts
    
    Creates specific tasks to test behavioral patterns:
    - Typing challenges
    - Mouse movement challenges
    - Cognitive challenges
    - Navigation challenges
    """
    
    # Sample sentences for typing challenges
    TYPING_SENTENCES = [
        "The quick brown fox jumps over the lazy dog",
        "Pack my box with five dozen liquor jugs",
        "How vexingly quick daft zebras jump",
        "The five boxing wizards jump quickly",
        "Sphinx of black quartz, judge my vow",
        "Two driven jocks help fax my big quiz",
        "The jay, pig, fox, zebra and my wolves quack",
        "Jackdaws love my big sphinx of quartz",
        "Mr. Jock, TV quiz PhD, bags few lynx",
        "Waltz, bad nymph, for quick jigs vex"
    ]
    
    # Cognitive questions
    COGNITIVE_QUESTIONS = [
        {
            "question": "Which of these websites do you access most frequently?",
            "type": "multiple_choice",
            "options": ["gmail.com", "facebook.com", "amazon.com", "github.com", "netflix.com"]
        },
        {
            "question": "How many passwords do you typically store in your vault?",
            "type": "range",
            "min": 0,
            "max": 500
        },
        {
            "question": "When do you typically access your password vault?",
            "type": "multiple_choice",
            "options": ["Morning", "Afternoon", "Evening", "Night", "Anytime"]
        },
        {
            "question": "How do you typically organize your passwords?",
            "type": "multiple_choice",
            "options": ["By category", "By website", "By importance", "Alphabetically", "No organization"]
        }
    ]
    
    def generate_challenge(self, recovery_attempt, challenge_type=None):
        """
        Generate a new behavioral challenge
        
        Args:
            recovery_attempt: BehavioralRecoveryAttempt object
            challenge_type: Specific type or None for auto-selection
        
        Returns:
            BehavioralChallenge object
        """
        if challenge_type is None:
            challenge_type = self._select_next_challenge_type(recovery_attempt)
        
        logger.info(f"Generating {challenge_type} challenge for attempt {recovery_attempt.attempt_id}")
        
        # Generate challenge data based on type
        if challenge_type == 'typing':
            challenge_data = self._generate_typing_challenge()
        elif challenge_type == 'mouse':
            challenge_data = self._generate_mouse_challenge()
        elif challenge_type == 'cognitive':
            challenge_data = self._generate_cognitive_challenge()
        elif challenge_type == 'navigation':
            challenge_data = self._generate_navigation_challenge()
        else:
            raise ValueError(f"Unknown challenge type: {challenge_type}")
        
        # Create challenge
        challenge = BehavioralChallenge.objects.create(
            recovery_attempt=recovery_attempt,
            challenge_type=challenge_type,
            challenge_data=challenge_data
        )
        
        return challenge
    
    def get_next_challenge(self, recovery_attempt):
        """
        Get the next challenge for a recovery attempt
        
        Args:
            recovery_attempt: BehavioralRecoveryAttempt object
        
        Returns:
            BehavioralChallenge object or None
        """
        # Check if recovery is complete
        if recovery_attempt.challenges_completed >= recovery_attempt.challenges_total:
            return None
        
        # Check if there's an uncompleted challenge
        uncompleted = BehavioralChallenge.objects.filter(
            recovery_attempt=recovery_attempt,
            completed_at__isnull=True
        ).first()
        
        if uncompleted:
            return uncompleted
        
        # Generate new challenge
        return self.generate_challenge(recovery_attempt)
    
    def _select_next_challenge_type(self, recovery_attempt):
        """
        Select the next challenge type based on progress
        
        Args:
            recovery_attempt: BehavioralRecoveryAttempt object
        
        Returns:
            str: Challenge type
        """
        completed = recovery_attempt.challenges_completed
        
        # Distribute challenges across types
        # First 5: typing
        if completed < 5:
            return 'typing'
        # Next 5: mouse
        elif completed < 10:
            return 'mouse'
        # Next 5: cognitive
        elif completed < 15:
            return 'cognitive'
        # Final 5: navigation
        else:
            return 'navigation'
    
    def _generate_typing_challenge(self):
        """Generate typing dynamics challenge"""
        sentence = random.choice(self.TYPING_SENTENCES)
        
        return {
            'type': 'typing',
            'instruction': 'Type the following sentence naturally:',
            'sentence': sentence,
            'expected_length': len(sentence),
            'capture_metrics': [
                'key_press_duration',
                'inter_key_latency',
                'typing_rhythm',
                'error_corrections',
                'shift_usage',
                'timing_patterns'
            ]
        }
    
    def _generate_mouse_challenge(self):
        """Generate mouse biometrics challenge"""
        tasks = [
            {
                'task': 'Click on the following buttons in order',
                'targets': [
                    {'label': 'Start', 'x': 100, 'y': 100},
                    {'label': 'Middle', 'x': 300, 'y': 200},
                    {'label': 'End', 'x': 500, 'y': 300}
                ]
            },
            {
                'task': 'Drag and drop these items',
                'items': ['Item 1', 'Item 2', 'Item 3']
            },
            {
                'task': 'Navigate through this menu',
                'menu_items': ['Home', 'Profile', 'Settings', 'Logout']
            }
        ]
        
        task = random.choice(tasks)
        
        return {
            'type': 'mouse',
            'instruction': task.get('task', 'Complete the mouse interaction'),
            'task_data': task,
            'capture_metrics': [
                'velocity_curves',
                'acceleration_patterns',
                'movement_trajectory',
                'click_timing',
                'hover_patterns',
                'mouse_jitter',
                'directional_preference'
            ]
        }
    
    def _generate_cognitive_challenge(self):
        """Generate cognitive pattern challenge"""
        question = random.choice(self.COGNITIVE_QUESTIONS)
        
        return {
            'type': 'cognitive',
            'instruction': 'Answer the following question',
            'question': question['question'],
            'question_type': question['type'],
            'options': question.get('options'),
            'min': question.get('min'),
            'max': question.get('max'),
            'capture_metrics': [
                'decision_time',
                'response_certainty',
                'hover_patterns'
            ]
        }
    
    def _generate_navigation_challenge(self):
        """Generate UI navigation challenge"""
        navigation_tasks = [
            {
                'task': 'Find and click on "Security Settings"',
                'target': 'security_settings',
                'expected_path': ['Dashboard', 'Settings', 'Security']
            },
            {
                'task': 'Organize these password entries by category',
                'items': ['gmail.com', 'facebook.com', 'github.com', 'netflix.com'],
                'categories': ['Social', 'Work', 'Entertainment', 'Email']
            },
            {
                'task': 'Search for a specific password entry',
                'search_term': 'bank',
                'expected_actions': ['Click search', 'Type query', 'Select result']
            }
        ]
        
        task = random.choice(navigation_tasks)
        
        return {
            'type': 'navigation',
            'instruction': task['task'],
            'task_data': task,
            'capture_metrics': [
                'navigation_sequence',
                'decision_speed',
                'path_efficiency',
                'interaction_patterns'
            ]
        }

