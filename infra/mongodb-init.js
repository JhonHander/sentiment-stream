/**
 * mongodb-init.js — MongoDB initialization script
 * Runs automatically on first container startup via Docker entrypoint.
 * Creates collections, indexes, and optional schema validation.
 */

/* eslint-disable no-undef */

db = db.getSiblingDB('sentiment_stream');

// ---------------------------------------------------------------------------
// predictions collection
// ---------------------------------------------------------------------------
db.createCollection('predictions', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['original_text', 'prediction', 'confidence', 'timestamp', 'model_version'],
      properties: {
        original_text: {
          bsonType: 'string',
          description: 'Texto original analizado — requerido',
        },
        prediction: {
          enum: ['positivo', 'negativo', 'neutral'],
          description: 'Clase de sentimiento predicha — requerido',
        },
        confidence: {
          bsonType: 'double',
          minimum: 0,
          maximum: 1,
          description: 'Confianza de la predicción entre 0 y 1 — requerido',
        },
        timestamp: {
          bsonType: 'date',
          description: 'Fecha/hora UTC de la predicción — requerido',
        },
        model_version: {
          bsonType: 'string',
          description: 'Versión del modelo usado — requerido',
        },
      },
    },
  },
  validationLevel: 'moderate',
  validationAction: 'warn',
});

// Indexes for predictions
db.predictions.createIndex({ timestamp: -1 }, { name: 'idx_predictions_timestamp_desc' });
db.predictions.createIndex({ prediction: 1 }, { name: 'idx_predictions_prediction_asc' });
db.predictions.createIndex({ confidence: -1 }, { name: 'idx_predictions_confidence_desc' });
db.predictions.createIndex(
  { original_text: 'text' },
  { name: 'idx_predictions_text', weights: { original_text: 10 } }
);

// ---------------------------------------------------------------------------
// model_metrics collection
// ---------------------------------------------------------------------------
db.createCollection('model_metrics');

db.model_metrics.createIndex(
  { model_version: 1 },
  { unique: true, name: 'idx_model_metrics_version_unique' }
);
db.model_metrics.createIndex({ trained_at: -1 }, { name: 'idx_model_metrics_trained_desc' });

print('MongoDB initialization complete: sentiment_stream database ready.');
