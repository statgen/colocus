class CoreRouter:
  """
  Router to direct models to the core database and
  all other models to the default database.
  """
  
  def db_for_read(self, model, **hints):
    """Send reads to the appropriate database."""
    if model._meta.app_label == 'core':
      return 'core'

    return 'default'
    
  def db_for_write(self, model, **hints):
    """Send writes to the appropriate database."""
    if model._meta.app_label == 'core':
      return 'core'

    return 'default'
    
  def allow_relation(self, obj1, obj2, **hints):
    """Allow relations if models are in the same database."""
    if obj1._meta.app_label == obj2._meta.app_label:
      return True

    return None
    
  def allow_migrate(self, db, app_label, model_name=None, **hints):
    """Ensure core models only appear in the core database."""
    if app_label == 'core':
      return db == 'core'

    return db == 'default'