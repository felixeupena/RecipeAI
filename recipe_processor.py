import os
import re
from typing import List, Dict
from pypdf import PdfReader


class RecipeProcessor:
    """Process recipe files (PDF and text) and extract recipe information."""
    
    def __init__(self):
        self.recipes = []
    
    def extract_recipes_from_text(self, text: str) -> List[Dict]:
        """Extract individual recipes from text content."""
        recipes = []

        # Strategy A: Cookbook-style — split on "Prep Time:" which reliably appears at the
        # top of each recipe. The non-empty line right above is the title.
        cookbook_blocks = self._split_cookbook_style(text)
        if len(cookbook_blocks) >= 2:
            for block in cookbook_blocks:
                if len(block.strip()) < 30:
                    continue
                recipe = self._parse_recipe_block(block)
                if recipe:
                    recipes.append(recipe)
            if recipes:
                return recipes

        # Strategy B: Original delimiter-based splitting
        recipe_blocks = re.split(r'\n(?=Recipe:|Title:|##\s+[A-Z]|\d+\.\s+[A-Z])', text, flags=re.IGNORECASE)

        if len(recipe_blocks) == 1:
            recipe_blocks = re.split(r'\n\d+\.\s+', text)

        if len(recipe_blocks) == 1:
            recipe_blocks = text.split('\n\n')

        for block in recipe_blocks:
            if len(block.strip()) < 30:
                continue
            recipe = self._parse_recipe_block(block)
            if recipe:
                recipes.append(recipe)

        # Fallback: store entire document as a single recipe
        if not recipes and len(text.strip()) > 100:
            recipes.append({
                'title': 'Cookbook Contents',
                'ingredients': ['See full text'],
                'instructions': ['See full text'],
                'cuisine': 'Various',
                'dietary': ['None'],
                'prep_time': 'N/A',
                'cook_time': 'N/A',
                'servings': 'N/A',
                'full_text': text.strip()
            })

        return recipes

    def _split_cookbook_style(self, text: str) -> List[str]:
        """Split text into recipe blocks for cookbooks where each recipe starts with
        a title line followed by 'Prep Time:'."""
        lines = text.split('\n')
        # Find indexes where 'Prep Time' appears
        prep_indexes = [i for i, l in enumerate(lines) if re.match(r'\s*Prep\s*Time\s*:', l, re.IGNORECASE)]
        if len(prep_indexes) < 2:
            return []

        # Determine the title line for each recipe (closest non-empty line above prep_time)
        starts = []
        for pi in prep_indexes:
            j = pi - 1
            while j >= 0 and not lines[j].strip():
                j -= 1
            starts.append(j if j >= 0 else pi)

        # Build blocks from start[k] to start[k+1]-1
        blocks = []
        for k, s in enumerate(starts):
            end = starts[k + 1] if k + 1 < len(starts) else len(lines)
            block = '\n'.join(lines[s:end]).strip()
            if block:
                blocks.append(block)
        return blocks
    
    def _parse_recipe_block(self, block: str) -> Dict:
        """Parse a single recipe block into structured data."""
        lines = [l for l in block.strip().split('\n')]

        recipe = {
            'title': '',
            'ingredients': [],
            'instructions': [],
            'cuisine': '',
            'dietary': [],
            'prep_time': '',
            'cook_time': '',
            'servings': '',
            'full_text': block.strip()
        }

        current_section = None

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue

            # Section headers (with or without colon, on their own line)
            if re.match(r'^(title|recipe|name)\s*:', line, re.IGNORECASE):
                recipe['title'] = re.sub(r'^(title|recipe|name)\s*:\s*', '', line, flags=re.IGNORECASE)
                continue
            if re.match(r'^(ingredients|material|what you need)\s*:?\s*$', line, re.IGNORECASE):
                current_section = 'ingredients'
                continue
            if re.match(r'^(instructions|directions|method|how to make|procedure|steps)\s*:?\s*$', line, re.IGNORECASE):
                current_section = 'instructions'
                continue

            # Metadata lines
            if re.match(r'^(cuisine|style|type)\s*:', line, re.IGNORECASE):
                recipe['cuisine'] = re.sub(r'^(cuisine|style|type)\s*:\s*', '', line, flags=re.IGNORECASE)
                continue
            if re.match(r'^(dietary|tags|restrictions)\s*:', line, re.IGNORECASE):
                dietary_text = re.sub(r'^(dietary|tags|restrictions)\s*:\s*', '', line, flags=re.IGNORECASE)
                recipe['dietary'] = [tag.strip() for tag in dietary_text.split(',')]
                continue
            if re.match(r'^(prep|preparation)\s*time\s*:', line, re.IGNORECASE):
                recipe['prep_time'] = re.sub(r'^(prep|preparation)\s*time\s*:\s*', '', line, flags=re.IGNORECASE)
                continue
            if re.match(r'^(cook|cooking)\s*time\s*:', line, re.IGNORECASE):
                recipe['cook_time'] = re.sub(r'^(cook|cooking)\s*time\s*:\s*', '', line, flags=re.IGNORECASE)
                continue
            if re.match(r'^total\s*time\s*:', line, re.IGNORECASE):
                # Skip — keep prep/cook separately
                continue
            if re.match(r'^(servings?|yields?)\s*:', line, re.IGNORECASE):
                recipe['servings'] = re.sub(r'^(servings?|yields?)\s*:\s*', '', line, flags=re.IGNORECASE)
                continue

            # Section content
            if current_section == 'ingredients':
                # Strip leading numbering/bullets like "1.", "1)", "-", "•"
                cleaned = re.sub(r'^[\-\u2022\d]+[\.\)]?\s*', '', line)
                if cleaned:
                    recipe['ingredients'].append(cleaned)
            elif current_section == 'instructions':
                cleaned = re.sub(r'^\d+[\.\)]\s*', '', line)
                if cleaned:
                    recipe['instructions'].append(cleaned)

        # Title fallback: first non-metadata line
        if not recipe['title']:
            for l in lines:
                t = l.strip()
                if not t:
                    continue
                if re.match(r'^(prep|cook|total)\s*time\s*:', t, re.IGNORECASE) or \
                   re.match(r'^(yield|servings?)\s*:', t, re.IGNORECASE) or \
                   re.match(r'^(ingredients|instructions)', t, re.IGNORECASE):
                    continue
                recipe['title'] = t[:80]
                break

        if not recipe['ingredients']:
            recipe['ingredients'] = ['See full text']
        if not recipe['instructions']:
            recipe['instructions'] = ['See full text']
        if not recipe['cuisine']:
            recipe['cuisine'] = 'Various'

        return recipe if recipe['title'] else None
    
    def process_pdf(self, file_path: str) -> List[Dict]:
        """Extract text from PDF and process recipes."""
        try:
            reader = PdfReader(file_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            
            return self.extract_recipes_from_text(text)
        except Exception as e:
            print(f"Error processing PDF {file_path}: {e}")
            return []
    
    def process_text_file(self, file_path: str) -> List[Dict]:
        """Process a text file and extract recipes."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
            
            return self.extract_recipes_from_text(text)
        except Exception as e:
            print(f"Error processing text file {file_path}: {e}")
            return []
    
    def process_file(self, file_path: str) -> List[Dict]:
        """Process a file based on its extension."""
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext == '.pdf':
            return self.process_pdf(file_path)
        elif ext in ['.txt', '.md']:
            return self.process_text_file(file_path)
        else:
            print(f"Unsupported file format: {ext}")
            return []
    
    def create_recipe_documents(self, recipes: List[Dict]) -> List[Dict]:
        """Convert recipes to document format for vector database."""
        documents = []
        
        for recipe in recipes:
            # Ensure dietary is not empty for ChromaDB
            dietary = recipe['dietary'] if recipe['dietary'] else ['None']
            ingredients = recipe['ingredients'] if recipe['ingredients'] else ['None']
            instructions = recipe['instructions'] if recipe['instructions'] else ['None']
            
            # Create a searchable text representation
            searchable_text = f"""
Recipe: {recipe['title']}
Cuisine: {recipe['cuisine']}
Dietary: {', '.join(dietary)}
Prep Time: {recipe['prep_time']}
Cook Time: {recipe['cook_time']}
Servings: {recipe['servings']}
Ingredients: {', '.join(ingredients)}
Instructions: {' '.join(instructions)}
""".strip()
            
            doc = {
                'page_content': searchable_text,
                'metadata': {
                    'title': recipe['title'],
                    'cuisine': recipe['cuisine'],
                    'dietary': dietary,
                    'ingredients': ingredients,
                    'prep_time': recipe['prep_time'],
                    'cook_time': recipe['cook_time'],
                    'servings': recipe['servings'],
                    'instructions': instructions
                }
            }
            documents.append(doc)
        
        return documents
