"""
Module consolidation analysis to recommend which modules should be combined
"""
import csv
import os
import logging
from collections import defaultdict
from pathlib import Path
import config

logger = logging.getLogger(__name__)


class ModuleConsolidationAnalyzer:
    """
    Analyzes modules to recommend consolidation based on:
    - Method override patterns (modules touching same models)
    - Field definitions (modules extending same models)
    - Dependencies
    - Logical grouping
    """
    
    def __init__(self, analysis_results_dir, eligible_modules=None):
        self.analysis_results_dir = analysis_results_dir
        self.method_overrides = []
        self.fields_data = []
        self.module_dependencies = []
        self.model_inheritance = []  # Direct inheritance relationships from CSV
        self.inheritance_data = {}  # Will be populated from model_inheritance
        
        # Determine eligible modules
        if eligible_modules is not None:
            self.eligible_modules = set(eligible_modules)
        else:
            self.eligible_modules = set(config.ELIGIBLE_MODULES_FOR_CORE) if config.ELIGIBLE_MODULES_FOR_CORE else set()
        
        if self.eligible_modules:
            logger.info(f"Consolidation analysis will only consider eligible modules: {sorted(self.eligible_modules)}")
        else:
            logger.warning("No eligible modules specified - consolidation analysis will consider all modules")
        
    def load_csv_data(self):
        """Load all relevant CSV files"""
        # Load method overrides
        methods_csv = os.path.join(self.analysis_results_dir, 'method_overrides.csv')
        if os.path.exists(methods_csv):
            with open(methods_csv, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                self.method_overrides = list(reader)
            logger.info(f"Loaded {len(self.method_overrides)} method override records")
        
        # Load fields analysis
        fields_csv = os.path.join(self.analysis_results_dir, 'fields_analysis.csv')
        if os.path.exists(fields_csv):
            with open(fields_csv, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                self.fields_data = list(reader)
            logger.info(f"Loaded {len(self.fields_data)} field definitions")
        
        # Load module dependencies
        deps_csv = os.path.join(self.analysis_results_dir, 'module_dependencies.csv')
        if os.path.exists(deps_csv):
            with open(deps_csv, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                self.module_dependencies = list(reader)
            logger.info(f"Loaded {len(self.module_dependencies)} module dependency records")
        
        # Load model inheritance relationships
        inheritance_csv = os.path.join(self.analysis_results_dir, 'model_inheritance.csv')
        if os.path.exists(inheritance_csv):
            with open(inheritance_csv, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                self.model_inheritance = list(reader)
            logger.info(f"Loaded {len(self.model_inheritance)} model inheritance relationships")
        
        # Extract inheritance data from model_inheritance CSV (more accurate than inferring from fields)
        self._extract_inheritance_data()
    
    def analyze_method_overlap(self):
        """
        Analyze which modules override the same methods on the same models.
        This indicates modules that 'touch' the same base code.
        Only considers eligible modules.
        """
        # Group by (model, method) -> list of modules
        method_groups = defaultdict(lambda: defaultdict(set))
        
        for method in self.method_overrides:
            model = method.get('model', '')
            method_name = method.get('method', '')
            module = method.get('module', '')
            
            # Only consider eligible modules
            if self.eligible_modules and module not in self.eligible_modules:
                continue
            
            if model and method_name and module:
                key = f"{model}.{method_name}"
                method_groups[key][module].add(method.get('file_path', ''))
        
        # Find methods that are overridden by multiple modules
        overlap_analysis = []
        for key, modules_dict in method_groups.items():
            if len(modules_dict) > 1:
                model, method_name = key.split('.', 1)
                modules = list(modules_dict.keys())
                file_count = sum(len(files) for files in modules_dict.values())
                
                overlap_analysis.append({
                    'model': model,
                    'method': method_name,
                    'modules': ', '.join(sorted(modules)),
                    'module_count': len(modules),
                    'total_overrides': file_count,
                    'severity': 'high' if len(modules) >= 3 else 'medium'
                })
        
        # Sort by severity and module count
        overlap_analysis.sort(key=lambda x: (x['severity'] == 'high', -x['module_count'], -x['total_overrides']))
        
        return overlap_analysis
    
    def analyze_model_touches(self):
        """
        Analyze which modules 'touch' (override methods or define fields for) the same models.
        Returns a matrix of module-to-model relationships.
        Only considers eligible modules.
        """
        # Track which models each module touches
        module_models = defaultdict(set)  # module -> set of models
        
        # From method overrides (only eligible modules)
        for method in self.method_overrides:
            model = method.get('model', '')
            module = method.get('module', '')
            
            # Only consider eligible modules
            if self.eligible_modules and module not in self.eligible_modules:
                continue
            
            if model and module:
                module_models[module].add(model)
        
        # From field definitions (only eligible modules)
        for field in self.fields_data:
            module = field.get('module', '')
            model = field.get('model', '')
            
            # Only consider eligible modules
            if self.eligible_modules and module not in self.eligible_modules:
                continue
            
            if model and module:
                module_models[module].add(model)
        
        # Find models touched by multiple modules
        model_modules = defaultdict(set)  # model -> set of modules
        for module, models in module_models.items():
            for model in models:
                model_modules[model].add(module)
        
        # Find models with high module overlap
        overlap_models = []
        for model, modules in model_modules.items():
            if len(modules) > 1:
                overlap_models.append({
                    'model': model,
                    'modules': ', '.join(sorted(modules)),
                    'module_count': len(modules),
                    'severity': 'high' if len(modules) >= 3 else 'medium'
                })
        
        overlap_models.sort(key=lambda x: (-x['module_count'], x['model']))
        
        return overlap_models, module_models
    
    def calculate_module_similarity(self, module_models):
        """
        Calculate similarity scores between modules based on:
        - Shared models (Jaccard similarity)
        - Shared method overrides
        - Dependencies
        Only considers eligible modules.
        """
        # Filter to only eligible modules
        if self.eligible_modules:
            modules = [m for m in module_models.keys() if m in self.eligible_modules]
        else:
            modules = list(module_models.keys())
        
        similarities = []
        
        for i, module1 in enumerate(modules):
            models1 = module_models[module1]
            if not models1:
                continue
                
            for module2 in modules[i+1:]:
                models2 = module_models[module2]
                if not models2:
                    continue
                
                # Jaccard similarity: intersection / union
                intersection = models1 & models2
                union = models1 | models2
                
                if union:
                    similarity = len(intersection) / len(union)
                    
                    # Count shared method overrides
                    shared_methods = self._count_shared_methods(module1, module2)
                    
                    # Check dependencies
                    has_dependency = self._check_dependency(module1, module2)
                    
                    similarities.append({
                        'module1': module1,
                        'module2': module2,
                        'similarity_score': similarity,
                        'shared_models': len(intersection),
                        'shared_models_list': ', '.join(sorted(intersection)),
                        'shared_methods': shared_methods,
                        'has_dependency': has_dependency,
                        'recommendation': self._get_consolidation_recommendation(
                            similarity, shared_methods, has_dependency
                        )
                    })
        
        # Sort by similarity score
        similarities.sort(key=lambda x: -x['similarity_score'])
        
        return similarities
    
    def _count_shared_methods(self, module1, module2):
        """Count how many methods are overridden by both modules on the same models"""
        # Only count if both modules are eligible
        if self.eligible_modules:
            if module1 not in self.eligible_modules or module2 not in self.eligible_modules:
                return 0
        
        methods1 = {(m['model'], m['method']) for m in self.method_overrides 
                   if m.get('module') == module1}
        methods2 = {(m['model'], m['method']) for m in self.method_overrides 
                   if m.get('module') == module2}
        
        return len(methods1 & methods2)
    
    def _check_dependency(self, module1, module2):
        """Check if module1 depends on module2 or vice versa"""
        for dep in self.module_dependencies:
            source = dep.get('source_module', '')
            target = dep.get('target_module', '')
            
            if (source == module1 and target == module2) or \
               (source == module2 and target == module1):
                return True
        return False
    
    def _get_consolidation_recommendation(self, similarity, shared_methods, has_dependency):
        """Generate recommendation based on similarity metrics"""
        if similarity >= 0.5 and shared_methods >= 3:
            return 'STRONG: High similarity and shared methods - consider consolidating'
        elif similarity >= 0.3 and shared_methods >= 2:
            return 'MODERATE: Moderate similarity - review for consolidation'
        elif has_dependency and similarity >= 0.2:
            return 'WEAK: Has dependency relationship - consider if related functionality'
        elif similarity >= 0.4:
            return 'WEAK: High similarity but few shared methods - review models'
        else:
            return 'LOW: Low similarity - keep separate'
    
    def generate_consolidation_groups(self, similarities, min_similarity=0.3):
        """
        Generate recommended consolidation groups based on similarity scores.
        Uses a greedy clustering approach.
        """
        # Filter to high similarity pairs
        high_similarity = [s for s in similarities 
                          if s['similarity_score'] >= min_similarity and 
                          s['recommendation'].startswith(('STRONG', 'MODERATE'))]
        
        # Build groups (greedy clustering)
        groups = []
        used_modules = set()
        
        for sim in high_similarity:
            module1 = sim['module1']
            module2 = sim['module2']
            
            # Skip if already in a group
            if module1 in used_modules or module2 in used_modules:
                continue
            
            # Create new group
            group = {
                'modules': sorted([module1, module2]),
                'similarity_score': sim['similarity_score'],
                'shared_models': sim['shared_models'],
                'shared_models_list': sim['shared_models_list'],
                'shared_methods': sim['shared_methods'],
                'recommendation': f"Consolidate {module1} and {module2}"
            }
            groups.append(group)
            used_modules.add(module1)
            used_modules.add(module2)
        
        # Sort by similarity
        groups.sort(key=lambda x: -x['similarity_score'])
        
        return groups
    
    def _extract_inheritance_data(self):
        """
        Extract inheritance information from model_inheritance CSV.
        This uses the actual _inherit declarations from Python files, which is more accurate
        than inferring from fields/methods.
        """
        # Use model_inheritance CSV which has direct _inherit relationships
        for inheritance in self.model_inheritance:
            module = inheritance.get('module', '')
            inherited_model = inheritance.get('inherited_model', '')
            inherited_module = inheritance.get('inherited_module', 'unknown')
            
            # Only consider eligible modules
            if self.eligible_modules and module not in self.eligible_modules:
                continue
            
            if not module or not inherited_model:
                continue
            
            # Only count as inherited if the inherited_model's module is NOT in eligible_modules
            # (i.e., it's a standard Odoo model like mail.thread, product.template, etc.)
            # OR if it's in a different eligible module
            if inherited_module not in self.eligible_modules or inherited_module != module:
                if module not in self.inheritance_data:
                    self.inheritance_data[module] = set()
                self.inheritance_data[module].add(inherited_model)
    
    def gather_module_statistics(self):
        """
        Gather key statistics for each eligible module to help with consolidation decisions.
        Returns statistics including:
        - File counts (Python, XML)
        - Lines of code
        - View counts
        - Inheritance patterns
        - Field counts
        - Method override counts
        """
        import config
        from pathlib import Path
        
        stats = []
        
        for module in sorted(self.eligible_modules):
            module_stat = {
                'module': module,
                'python_files': 0,
                'xml_files': 0,
                'lines_of_code': 0,
                'view_count': 0,
                'field_count': 0,
                'method_override_count': 0,
                'inherited_models': set(),
                'models_defined': set(),
                'shared_inherited_models': []  # Will be filled later
            }
            
            # Count fields
            for field in self.fields_data:
                if field.get('module') == module:
                    module_stat['field_count'] += 1
                    model = field.get('model', '')
                    if model:
                        module_stat['models_defined'].add(model)
            
            # Count method overrides
            for method in self.method_overrides:
                if method.get('module') == module:
                    module_stat['method_override_count'] += 1
                    model = method.get('model', '')
                    if model:
                        module_stat['models_defined'].add(model)
            
            # Get inheritance data
            if module in self.inheritance_data:
                module_stat['inherited_models'] = self.inheritance_data[module]
                # Also add inherited models to models_defined since the module is "touching" them
                for inherited_model in self.inheritance_data[module]:
                    module_stat['models_defined'].add(inherited_model)
            
            # Count files and lines of code
            if config.BASE_DIR:
                module_paths = self._find_module_paths(module, config.BASE_DIR)
                for module_path in module_paths:
                    python_count, xml_count, loc = self._count_module_files(module_path)
                    module_stat['python_files'] += python_count
                    module_stat['xml_files'] += xml_count
                    module_stat['lines_of_code'] += loc
                    
                    # Count views (rough estimate from XML files)
                    module_stat['view_count'] += self._count_views_in_module(module_path)
            
            # Convert sets to strings for CSV
            module_stat['inherited_models_list'] = ', '.join(sorted(module_stat['inherited_models']))
            module_stat['inherited_models_count'] = len(module_stat['inherited_models'])
            module_stat['models_defined_list'] = ', '.join(sorted(module_stat['models_defined']))
            module_stat['models_defined_count'] = len(module_stat['models_defined'])
            
            # Remove set objects (not JSON serializable)
            del module_stat['inherited_models']
            del module_stat['models_defined']
            
            stats.append(module_stat)
        
        # Calculate shared inherited models between modules
        self._calculate_inheritance_overlap(stats)
        
        return stats
    
    def _find_module_paths(self, module_name, base_dir):
        """Find all paths that might contain this module"""
        from pathlib import Path
        import os
        
        paths = []
        base_path = Path(base_dir)
        
        # Look for module in common locations
        search_dirs = ['user', 'odoo', 'enterprise', 'custom']
        
        for search_dir in search_dirs:
            potential_path = base_path / search_dir / module_name
            if potential_path.exists() and (potential_path / '__manifest__.py').exists():
                paths.append(potential_path)
        
        # Also check direct subdirectories
        for item in base_path.iterdir():
            if item.is_dir():
                potential_path = item / module_name
                if potential_path.exists() and (potential_path / '__manifest__.py').exists():
                    if potential_path not in paths:
                        paths.append(potential_path)
        
        return paths
    
    def _count_module_files(self, module_path):
        """Count Python and XML files and lines of code in a module"""
        from pathlib import Path
        
        python_count = 0
        xml_count = 0
        loc = 0
        
        if not module_path.exists():
            return python_count, xml_count, loc
        
        # Count Python files (exclude __init__.py and __manifest__.py)
        for py_file in module_path.rglob('*.py'):
            # Skip __pycache__, __init__.py, __manifest__.py, and test files
            if '__pycache__' in str(py_file):
                continue
            if py_file.name in ('__init__.py', '__manifest__.py'):
                continue
            if 'test_' in py_file.name:
                continue
            python_count += 1
            try:
                with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                    loc += len([line for line in f if line.strip()])
            except:
                pass
        
        # Count XML files
        for xml_file in module_path.rglob('*.xml'):
            xml_count += 1
        
        return python_count, xml_count, loc
    
    def _count_views_in_module(self, module_path):
        """Count views in XML files"""
        from pathlib import Path
        import xml.etree.ElementTree as ET
        
        view_count = 0
        seen_records = set()  # Track to avoid double counting
        
        for xml_file in module_path.rglob('*.xml'):
            try:
                # Try to parse and count actual view records
                tree = ET.parse(xml_file)
                root = tree.getroot()
                
                # Count <record> elements with model="ir.ui.view" (case-insensitive)
                for record in root.findall(".//record"):
                    model = record.get('model', '')
                    if model and 'ir.ui.view' in model.lower():
                        # Use record ID to avoid double counting
                        record_id = record.get('id', '')
                        if record_id:
                            key = f"{xml_file}:{record_id}"
                            if key not in seen_records:
                                seen_records.add(key)
                                view_count += 1
                        else:
                            # No ID, just count it
                            view_count += 1
            except:
                # Fallback: simple text search
                try:
                    with open(xml_file, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        # Count <record> elements with model="ir.ui.view"
                        # Use a simple regex-like approach to avoid double counting
                        view_count += max(
                            content.count('model="ir.ui.view"'),
                            content.count("model='ir.ui.view'")
                        )
                except:
                    pass
        
        return view_count
    
    def _calculate_inheritance_overlap(self, stats):
        """Calculate which modules share inherited models"""
        # Build a map of inherited_model -> list of modules
        model_to_modules = defaultdict(list)
        for stat in stats:
            inherited_list = stat.get('inherited_models_list', '')
            if inherited_list:
                for model in inherited_list.split(', '):
                    if model:
                        model_to_modules[model].append(stat['module'])
        
        # Store model_to_modules for later use in summary export
        self.model_to_modules = model_to_modules
        
        # For each module, find shared inherited models
        for stat in stats:
            module = stat['module']
            shared_models = []
            
            for model, modules in model_to_modules.items():
                if len(modules) > 1 and module in modules:
                    # This model is inherited by multiple modules
                    other_modules = [m for m in modules if m != module]
                    shared_models.append(f"{model} (with {', '.join(other_modules)})")
            
            stat['shared_inherited_models'] = '; '.join(shared_models) if shared_models else ''
            stat['shared_inherited_models_count'] = len(shared_models)
    
    def _generate_inherited_model_summary(self, stats):
        """
        Generate a summary of inherited models showing which modules inherit each model
        and which modules share each inherited model.
        
        Returns a list of dictionaries with:
        - inherited_model: The model being inherited
        - modules_inheriting: Comma-separated list of modules that inherit this model
        - module_count: Number of modules inheriting this model
        - is_shared: Whether this model is shared by multiple modules (True/False)
        - sharing_details: Details about which modules share this model
        """
        summary = []
        
        # Use the model_to_modules map built in _calculate_inheritance_overlap
        if not hasattr(self, 'model_to_modules'):
            # If not available, rebuild it
            model_to_modules = defaultdict(list)
            for stat in stats:
                inherited_list = stat.get('inherited_models_list', '')
                if inherited_list:
                    for model in inherited_list.split(', '):
                        if model:
                            model_to_modules[model].append(stat['module'])
            self.model_to_modules = model_to_modules
        
        # Generate summary for each inherited model
        for model, modules in sorted(self.model_to_modules.items()):
            modules_sorted = sorted(set(modules))  # Remove duplicates and sort
            module_count = len(modules_sorted)
            is_shared = module_count > 1
            
            # Build sharing details
            if is_shared:
                sharing_details = f"Shared by {module_count} modules: {', '.join(modules_sorted)}"
            else:
                sharing_details = f"Inherited only by {modules_sorted[0]}"
            
            summary.append({
                'inherited_model': model,
                'modules_inheriting': ', '.join(modules_sorted),
                'module_count': module_count,
                'is_shared': 'Yes' if is_shared else 'No',
                'sharing_details': sharing_details
            })
        
        return summary
    
    def analyze(self):
        """Run full consolidation analysis"""
        logger.info("Analyzing module consolidation opportunities...")
        
        # Gather module statistics first
        module_stats = self.gather_module_statistics()
        logger.info(f"Gathered statistics for {len(module_stats)} eligible modules")
        
        # Analyze method overlaps
        method_overlaps = self.analyze_method_overlap()
        logger.info(f"Found {len(method_overlaps)} methods overridden by multiple modules")
        
        # Analyze model touches
        model_overlaps, module_models = self.analyze_model_touches()
        logger.info(f"Found {len(model_overlaps)} models touched by multiple modules")
        
        # Calculate module similarities
        similarities = self.calculate_module_similarity(module_models)
        logger.info(f"Calculated {len(similarities)} module similarity pairs")
        
        # Generate consolidation groups
        consolidation_groups = self.generate_consolidation_groups(similarities)
        logger.info(f"Generated {len(consolidation_groups)} consolidation recommendations")
        
        return {
            'module_statistics': module_stats,
            'method_overlaps': method_overlaps,
            'model_overlaps': model_overlaps,
            'module_similarities': similarities,
            'consolidation_groups': consolidation_groups
        }
    
    def export_to_csv(self, results, output_dir):
        """Export consolidation analysis to CSV files"""
        os.makedirs(output_dir, exist_ok=True)
        
        # Export module statistics
        if results.get('module_statistics'):
            with open(os.path.join(output_dir, 'module_statistics.csv'), 'w', newline='', encoding='utf-8') as f:
                fieldnames = ['module', 'python_files', 'xml_files', 'lines_of_code', 'view_count',
                             'field_count', 'method_override_count', 'inherited_models_count',
                             'inherited_models_list', 'models_defined_count', 'models_defined_list',
                             'shared_inherited_models_count', 'shared_inherited_models']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(results['module_statistics'])
            logger.info(f"Exported statistics for {len(results['module_statistics'])} modules")
            
            # Export inherited model summary
            inherited_model_summary = self._generate_inherited_model_summary(results['module_statistics'])
            if inherited_model_summary:
                with open(os.path.join(output_dir, 'inherited_models_summary.csv'), 'w', newline='', encoding='utf-8') as f:
                    fieldnames = ['inherited_model', 'modules_inheriting', 'module_count', 'is_shared', 'sharing_details']
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(inherited_model_summary)
                logger.info(f"Exported inherited model summary for {len(inherited_model_summary)} models")
        
        # Export method overlaps
        if results.get('method_overlaps'):
            with open(os.path.join(output_dir, 'method_overlaps.csv'), 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['model', 'method', 'modules', 'module_count', 
                                                       'total_overrides', 'severity'])
                writer.writeheader()
                writer.writerows(results['method_overlaps'])
            logger.info(f"Exported {len(results['method_overlaps'])} method overlap records")
        
        # Export model overlaps
        if results.get('model_overlaps'):
            with open(os.path.join(output_dir, 'model_overlaps.csv'), 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['model', 'modules', 'module_count', 'severity'])
                writer.writeheader()
                writer.writerows(results['model_overlaps'])
            logger.info(f"Exported {len(results['model_overlaps'])} model overlap records")
        
        # Export module similarities
        if results.get('module_similarities'):
            with open(os.path.join(output_dir, 'module_similarities.csv'), 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['module1', 'module2', 'similarity_score', 
                                                       'shared_models', 'shared_models_list', 
                                                       'shared_methods', 'has_dependency', 'recommendation'])
                writer.writeheader()
                writer.writerows(results['module_similarities'])
            logger.info(f"Exported {len(results['module_similarities'])} module similarity records")
        
        # Export consolidation groups
        if results.get('consolidation_groups'):
            with open(os.path.join(output_dir, 'consolidation_groups.csv'), 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['modules', 'similarity_score', 'shared_models', 
                                                       'shared_models_list', 'shared_methods', 'recommendation'])
                writer.writeheader()
                writer.writerows(results['consolidation_groups'])
            logger.info(f"Exported {len(results['consolidation_groups'])} consolidation group recommendations")


def analyze_module_consolidation(analysis_results_dir, output_dir, eligible_modules=None):
    """
    Main function to analyze module consolidation opportunities
    
    Args:
        analysis_results_dir: Directory containing CSV analysis results
        output_dir: Directory to write consolidation analysis files
        eligible_modules: Optional list of module names eligible for consolidation.
                        If None, uses config.ELIGIBLE_MODULES_FOR_CORE.
    """
    analyzer = ModuleConsolidationAnalyzer(analysis_results_dir, eligible_modules)
    analyzer.load_csv_data()
    results = analyzer.analyze()
    analyzer.export_to_csv(results, output_dir)
    
    return results

