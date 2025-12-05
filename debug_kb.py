import sys
import os
sys.path.append(os.getcwd())
from src.knowledge_manager import KnowledgeManager

km = KnowledgeManager()
info = km.get_class_info('SignalServiceTranslationProps')
print("Created By:", info.get('created_by'))
print("References:", info.get('references'))
