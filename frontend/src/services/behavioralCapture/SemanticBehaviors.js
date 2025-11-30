/**
 * Semantic Behaviors Capture
 * 
 * Captures 32+ dimensional semantic behavior patterns including:
 * - Password creation patterns
 * - Vault organization methodology
 * - Search formulation style
 * - Auto-fill usage
 */

export class SemanticBehaviors {
  constructor() {
    this.passwordCreations = [];
    this.vaultOrganizations = [];
    this.searchBehaviors = [];
    this.autoFillEvents = [];
    
    // Statistics
    this.stats = {
      // Password creation patterns
      passwordsCreated: 0,
      passwordLengthDistribution: [],
      characterTypePreferences: {
        uppercase: 0,
        lowercase: 0,
        numbers: 0,
        special: 0
      },
      passwordComplexityPreferences: [],
      
      // Vault organization
      foldersCreated: 0,
      itemsOrganized: 0,
      folderHierarchyDepth: [],
      namingConventions: [],
      tagsUsed: new Set(),
      favoritesMarked: 0,
      
      // Category preferences
      categoryUsage: new Map(),
      
      // Search formulation
      searches: [],
      avgSearchLength: 0,
      searchTermTypes: {
        exact: 0,
        partial: 0,
        category: 0
      },
      searchRefinements: 0,
      
      // Auto-fill behavior
      autoFillAccepted: 0,
      autoFillRejected: 0,
      autoFillModified: 0,
      
      // Entry editing patterns
      edits: [],
      quickEdits: 0, // < 10 seconds
      thoroughEdits: 0, // > 30 seconds
      fieldsEdited: new Map(),
      
      // Copy-paste for passwords
      passwordCopies: 0,
      
      // Session metadata
      startTime: null,
      lastActivity: null
    };
    
    this.isAttached = false;
  }
  
  /**
   * Attach listeners (passive observation of vault operations)
   */
  attach() {
    if (this.isAttached) return;
    
    this.stats.startTime = Date.now();
    this.isAttached = true;
    
    console.log('SemanticBehaviors: Initialized (passive tracking)');
  }
  
  /**
   * Detach listeners
   */
  detach() {
    this.isAttached = false;
    console.log('SemanticBehaviors: Detached');
  }
  
  /**
   * Track password creation event
   */
  trackPasswordCreation(passwordData) {
    this.stats.passwordsCreated++;
    
    if (passwordData.length) {
      this.stats.passwordLengthDistribution.push(passwordData.length);
    }
    
    // Analyze character composition
    if (passwordData.composition) {
      const comp = passwordData.composition;
      if (comp.hasUppercase) this.stats.characterTypePreferences.uppercase++;
      if (comp.hasLowercase) this.stats.characterTypePreferences.lowercase++;
      if (comp.hasNumbers) this.stats.characterTypePreferences.numbers++;
      if (comp.hasSpecial) this.stats.characterTypePreferences.special++;
    }
    
    this.stats.lastActivity = Date.now();
  }
  
  /**
   * Track folder creation
   */
  trackFolderCreation(folderData) {
    this.stats.foldersCreated++;
    
    if (folderData.depth) {
      this.stats.folderHierarchyDepth.push(folderData.depth);
    }
    
    if (folderData.name) {
      this.stats.namingConventions.push({
        length: folderData.name.length,
        hasSpaces: folderData.name.includes(' '),
        hasSpecialChars: /[^a-zA-Z0-9\s]/.test(folderData.name)
      });
    }
    
    this.stats.lastActivity = Date.now();
  }
  
  /**
   * Track item organization
   */
  trackItemOrganization(organizationData) {
    this.stats.itemsOrganized++;
    
    if (organizationData.category) {
      const count = this.stats.categoryUsage.get(organizationData.category) || 0;
      this.stats.categoryUsage.set(organizationData.category, count + 1);
    }
    
    if (organizationData.tags) {
      organizationData.tags.forEach(tag => this.stats.tagsUsed.add(tag));
    }
    
    if (organizationData.isFavorite) {
      this.stats.favoritesMarked++;
    }
    
    this.stats.lastActivity = Date.now();
  }
  
  /**
   * Track search behavior
   */
  trackSearch(searchData) {
    this.stats.searches.push({
      query: searchData.query,
      length: searchData.query.length,
      timestamp: Date.now(),
      resultsCount: searchData.resultsCount || 0
    });
    
    // Categorize search type
    if (searchData.query.length < 3) {
      this.stats.searchTermTypes.partial++;
    } else if (/^[a-z]+$/i.test(searchData.query)) {
      this.stats.searchTermTypes.exact++;
    } else {
      this.stats.searchTermTypes.category++;
    }
    
    // Detect search refinements (multiple searches in short time)
    if (this.stats.searches.length >= 2) {
      const lastSearch = this.stats.searches[this.stats.searches.length - 2];
      const timeDiff = Date.now() - lastSearch.timestamp;
      
      if (timeDiff < 10000) { // Within 10 seconds
        this.stats.searchRefinements++;
      }
    }
    
    this.stats.lastActivity = Date.now();
  }
  
  /**
   * Track auto-fill behavior
   */
  trackAutoFill(autoFillData) {
    if (autoFillData.accepted) {
      this.stats.autoFillAccepted++;
    } else if (autoFillData.rejected) {
      this.stats.autoFillRejected++;
    } else if (autoFillData.modified) {
      this.stats.autoFillModified++;
    }
    
    this.stats.lastActivity = Date.now();
  }
  
  /**
   * Track entry editing
   */
  trackEntryEdit(editData) {
    const editDuration = editData.duration || 0;
    
    this.stats.edits.push({
      duration: editDuration,
      fieldsModified: editData.fieldsModified || [],
      timestamp: Date.now()
    });
    
    if (editDuration < 10) {
      this.stats.quickEdits++;
    } else if (editDuration > 30) {
      this.stats.thoroughEdits++;
    }
    
    // Track which fields are edited most
    if (editData.fieldsModified) {
      editData.fieldsModified.forEach(field => {
        this.stats.fieldsEdited.set(field, (this.stats.fieldsEdited.get(field) || 0) + 1);
      });
    }
    
    this.stats.lastActivity = Date.now();
  }
  
  /**
   * Track password copy event
   */
  trackPasswordCopy() {
    this.stats.passwordCopies++;
    this.stats.lastActivity = Date.now();
  }
  
  /**
   * Get semantic behavior features (32+ dimensions)
   */
  async getFeatures() {
    const sessionDuration = (this.stats.lastActivity - this.stats.startTime) / 1000;
    
    const features = {
      // Password creation patterns (8 dimensions)
      passwords_created: this.stats.passwordsCreated,
      avg_password_length: this._mean(this.stats.passwordLengthDistribution),
      password_length_variance: this._std(this.stats.passwordLengthDistribution),
      prefers_uppercase: this.stats.characterTypePreferences.uppercase / (this.stats.passwordsCreated + 1),
      prefers_lowercase: this.stats.characterTypePreferences.lowercase / (this.stats.passwordsCreated + 1),
      prefers_numbers: this.stats.characterTypePreferences.numbers / (this.stats.passwordsCreated + 1),
      prefers_special: this.stats.characterTypePreferences.special / (this.stats.passwordsCreated + 1),
      password_complexity_preference: this._calculateAvgComplexity(),
      
      // Vault organization (10 dimensions)
      folders_created: this.stats.foldersCreated,
      items_organized: this.stats.itemsOrganized,
      avg_folder_depth: this._mean(this.stats.folderHierarchyDepth),
      max_folder_depth: Math.max(0, ...this.stats.folderHierarchyDepth),
      tags_diversity: this.stats.tagsUsed.size,
      favorites_rate: this.stats.favoritesMarked / (this.stats.itemsOrganized + 1),
      organization_frequency: this.stats.itemsOrganized / (sessionDuration / 60),
      naming_avg_length: this._calculateAvgNamingLength(),
      uses_spaces_in_names: this._calculateSpaceUsageInNames(),
      organization_style: this._identifyOrganizationStyle(),
      
      // Search behavior (6 dimensions)
      search_count: this.stats.searches.length,
      avg_search_length: this._mean(this.stats.searches.map(s => s.length)),
      search_refinement_rate: this.stats.searches.length > 0
        ? this.stats.searchRefinements / this.stats.searches.length
        : 0,
      exact_search_preference: this.stats.searchTermTypes.exact / (this.stats.searches.length + 1),
      partial_search_preference: this.stats.searchTermTypes.partial / (this.stats.searches.length + 1),
      category_search_preference: this.stats.searchTermTypes.category / (this.stats.searches.length + 1),
      
      // Auto-fill behavior (4 dimensions)
      autofill_acceptance_rate: (this.stats.autoFillAccepted + this.stats.autoFillRejected + this.stats.autoFillModified) > 0
        ? this.stats.autoFillAccepted / (this.stats.autoFillAccepted + this.stats.autoFillRejected + this.stats.autoFillModified)
        : 0,
      autofill_modification_rate: (this.stats.autoFillAccepted + this.stats.autoFillRejected + this.stats.autoFillModified) > 0
        ? this.stats.autoFillModified / (this.stats.autoFillAccepted + this.stats.autoFillRejected + this.stats.autoFillModified)
        : 0,
      autofill_rejection_rate: (this.stats.autoFillAccepted + this.stats.autoFillRejected + this.stats.autoFillModified) > 0
        ? this.stats.autoFillRejected / (this.stats.autoFillAccepted + this.stats.autoFillRejected + this.stats.autoFillModified)
        : 0,
      autofill_usage_frequency: (this.stats.autoFillAccepted + this.stats.autoFillRejected + this.stats.autoFillModified) / (sessionDuration / 60),
      
      // Entry editing patterns (4 dimensions)
      total_edits: this.stats.edits.length,
      quick_edit_rate: this.stats.edits.length > 0
        ? this.stats.quickEdits / this.stats.edits.length
        : 0,
      thorough_edit_rate: this.stats.edits.length > 0
        ? this.stats.thoroughEdits / this.stats.edits.length
        : 0,
      avg_edit_duration: this._mean(this.stats.edits.map(e => e.duration)),
      
      // Metadata
      total_semantic_operations: this.stats.passwordsCreated + this.stats.itemsOrganized + this.stats.searches.length,
      data_quality_score: this._assessDataQuality(),
      capture_timestamp: Date.now()
    };
    
    return features;
  }
  
  _calculateAvgComplexity() {
    if (this.stats.passwordComplexityPreferences.length === 0) return 0;
    return this._mean(this.stats.passwordComplexityPreferences);
  }
  
  _calculateAvgNamingLength() {
    if (this.stats.namingConventions.length === 0) return 0;
    const lengths = this.stats.namingConventions.map(n => n.length);
    return this._mean(lengths);
  }
  
  _calculateSpaceUsageInNames() {
    if (this.stats.namingConventions.length === 0) return 0;
    const withSpaces = this.stats.namingConventions.filter(n => n.hasSpaces).length;
    return withSpaces / this.stats.namingConventions.length;
  }
  
  _identifyOrganizationStyle() {
    const folderBased = this.stats.foldersCreated > 0;
    const tagBased = this.stats.tagsUsed.size > 3;
    const favoriteBased = this.stats.favoritesMarked > 5;
    
    if (folderBased && tagBased) return 'hierarchical_tagged';
    if (folderBased) return 'hierarchical';
    if (tagBased) return 'tag_based';
    if (favoriteBased) return 'favorite_based';
    return 'flat';
  }
  
  _assessDataQuality() {
    let quality = 0;
    
    // Password creation samples
    if (this.stats.passwordsCreated >= 3) quality += 0.3;
    else quality += (this.stats.passwordsCreated / 3) * 0.3;
    
    // Organization samples
    if (this.stats.itemsOrganized >= 5) quality += 0.3;
    else quality += (this.stats.itemsOrganized / 5) * 0.3;
    
    // Search samples
    if (this.stats.searches.length >= 3) quality += 0.2;
    else quality += (this.stats.searches.length / 3) * 0.2;
    
    // Edit samples
    if (this.stats.edits.length >= 2) quality += 0.2;
    else quality += (this.stats.edits.length / 2) * 0.2;
    
    return Math.min(quality, 1.0);
  }
}

