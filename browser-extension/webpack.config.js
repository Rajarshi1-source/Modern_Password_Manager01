const path = require('path');
const CopyPlugin = require('copy-webpack-plugin');

module.exports = {
  entry: {
    background: './src/background.js',
    content: './src/content.js',
    popup: './src/popup.js',
    options: './src/options.js'
  },
  output: {
    path: path.resolve(__dirname, 'dist'),
    filename: '[name].js',
    clean: true
  },
  module: {
    rules: [
      {
        test: /\.js$/,
        exclude: /node_modules/,
        use: {
          loader: 'babel-loader',
          options: {
            presets: ['@babel/preset-env']
          }
        }
      },
      {
        test: /\.css$/,
        use: ['style-loader', 'css-loader']
      }
    ]
  },
  resolve: {
    extensions: ['.js', '.json'],
    alias: {
      // Shared code with the main app
      '@shared': path.resolve(__dirname, '../shared'),
      // To use code from frontend app
      '@frontend': path.resolve(__dirname, '../frontend/src')
    }
  },
  plugins: [
    new CopyPlugin({
      patterns: [
        { from: 'manifest.json', to: '' },
        { from: 'src/icons', to: 'icons', noErrorOnMissing: true },
        { from: 'src/popup.html', to: '', noErrorOnMissing: true },
        { from: 'src/options.html', to: '', noErrorOnMissing: true }
      ]
    })
  ]
};
