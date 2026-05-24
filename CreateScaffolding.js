const fs = require('fs');
const path = require('path');

// Load the blueprint configuration
const blueprintPath = path.join(__dirname, 'Directory.json');
if (!fs.existsSync(blueprintPath)) {
  console.error("Error: structure.json file not found!");
  process.exit(1);
}

const structure = JSON.parse(fs.readFileSync(blueprintPath, 'utf8'));

// Recursive function to build folders and files
function buildStructure(basePath, obj) {
  for (const key in obj) {
    const currentPath = path.join(basePath, key);

    if (typeof obj[key] === 'object' && obj[key] !== null && !Array.isArray(obj[key])) {
      // It's a directory: Create it if it doesn't exist, then recurse
      if (!fs.existsSync(currentPath)) {
        fs.mkdirSync(currentPath, { recursive: true });
        console.log(`📁 Created folder: ${currentPath}`);
      }
      buildStructure(currentPath, obj[key]);
    } else {
      // It's a file: Create it and populate content if provided
      const content = typeof obj[key] === 'string' ? obj[key] : '';
      fs.writeFileSync(currentPath, content, 'utf8');
      console.log(`📄 Created file:   ${currentPath}`);
    }
  }
}

console.log("🚀 Starting project scaffolding...");
buildStructure(__dirname, structure);
console.log("✨ Scaffolding complete!");