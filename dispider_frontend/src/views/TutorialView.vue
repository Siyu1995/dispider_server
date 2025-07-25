<template>
  <div class="tutorial-layout">
    <!-- Table of Contents Sidebar -->
    <div class="toc-sidebar">
      <el-card class="box-card">
        <template #header>
          <div class="card-header">
            <span>目录</span>
          </div>
        </template>
        <ul class="toc-list">
          <li
            v-for="(chapter, index) in chapters"
            :key="index"
            :class="{ active: index === currentChapterIndex }"
            @click="goToChapter(index)"
          >
            {{ chapter.title }}
          </li>
        </ul>
      </el-card>
    </div>

    <!-- Scrollable Content Area -->
    <div class="content-main">
      <el-card class="box-card">
        <div v-if="chapters.length > 0" class="chapter-content">
          <div
            class="markdown-body"
            v-html="chapters[currentChapterIndex].html"
          ></div>
          <el-divider />
          <div class="navigation-buttons">
            <el-button
              :disabled="currentChapterIndex === 0"
              @click="prevChapter"
            >
              <el-icon><ArrowLeft /></el-icon>
              上一章
            </el-button>
            <el-button
              :disabled="currentChapterIndex === chapters.length - 1"
              @click="nextChapter"
            >
              下一章
              <el-icon class="el-icon--right"><ArrowRight /></el-icon>
            </el-button>
          </div>
        </div>
        <div v-else>
          <p>正在加载教程...</p>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import { ArrowLeft, ArrowRight } from '@element-plus/icons-vue';

const tutorialContent = ref('');
const chapters = ref([]);
const currentChapterIndex = ref(0);

/**
 * Parses the raw Markdown content into chapters.
 * This new logic splits chapters based on H2 headings (##) 
 * making it robust against separators inside code blocks.
 */
const parseChapters = () => {
  // Split the entire document by H2 headings. 
  // The regex splits the string on newlines that are followed by `## `
  const sections = tutorialContent.value.split(/\n(?=##\s)/);

  const parsedChapters = [];
  
  sections.forEach(sectionText => {
      if (!sectionText.trim()) return;

      const titleMatch = sectionText.match(/^##\s+(.*)/m);
      
      if (titleMatch) {
          // This is a chapter with a title
          const title = titleMatch[1];
          parsedChapters.push({
              title: title.replace(/ \(.+\)/, ''), // Remove " (xyz)" from title
              html: DOMPurify.sanitize(marked(sectionText)),
          });
      } else if (parsedChapters.length === 0) {
          // This is content before the first H2, treat as Introduction
           parsedChapters.push({
              title: '介绍',
              html: DOMPurify.sanitize(marked(sectionText)),
          });
      }
  });

  chapters.value = parsedChapters;
};

/**
 * Fetches the tutorial Markdown file from the server.
 */
const fetchTutorial = async () => {
  try {
    // We assume the tutorial file is in the public folder for direct access
    // This requires moving the .md file to the 'public' directory in the frontend project
    const response = await fetch('/QuickStartDispider.md');
    if (!response.ok) {
      throw new Error('教程文件加载失败。');
    }
    tutorialContent.value = await response.text();
    parseChapters();
  } catch (error) {
    console.error('无法获取教程:', error);
    chapters.value = [{ title: '错误', html: `<p>无法加载教程内容。请确保 <code>QuickStartDispider.md</code> 文件位于前端的 <code>public</code> 文件夹下。</p>` }];
  }
};

const goToChapter = (index) => {
  currentChapterIndex.value = index;
};

const nextChapter = () => {
  if (currentChapterIndex.value < chapters.value.length - 1) {
    currentChapterIndex.value++;
  }
};

const prevChapter = () => {
  if (currentChapterIndex.value > 0) {
    currentChapterIndex.value--;
  }
};

onMounted(() => {
  fetchTutorial();
});
</script>

<style scoped>
/* New Layout Styles */
.tutorial-layout {
  display: flex;
  height: 100vh;
  box-sizing: border-box;
  padding: 20px;
  gap: 20px;
}

.toc-sidebar {
  width: 15%;
  min-width: 150px;
  flex-shrink: 0;
}

.content-main {
  flex-grow: 1;
  overflow-y: auto; /* This creates the independent scrolling context */
}

.toc-sidebar .el-card {
  height: 100%;
}
/* End of New Layout Styles */

.toc-list {
  list-style-type: none;
  padding: 0;
}
.toc-list li {
  padding: 10px 15px;
  cursor: pointer;
  border-radius: 4px;
  transition: background-color 0.3s;
}
.toc-list li:hover {
  background-color: #f5f7fa;
}
.toc-list li.active {
  background-color: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  font-weight: bold;
}
.navigation-buttons {
  display: flex;
  justify-content: space-between;
  margin-top: 20px;
}

/* Styles for the rendered markdown content */
.markdown-body {
  line-height: 1.6;
}
.markdown-body :deep(h2) {
  font-size: 1.8em;
  border-bottom: 1px solid #eaecef;
  padding-bottom: 0.3em;
  margin-top: 24px;
  margin-bottom: 16px;
}
.markdown-body :deep(img) {
  border-radius: 12px;
  margin-bottom: 16px;
  margin-top: 16px;
}
.markdown-body :deep(h3) {
  font-size: 1.5em;
  margin-top: 24px;
  margin-bottom: 16px;
}
.markdown-body :deep(h4) {
  font-size: 1.2em;
  margin-top: 16px;
  margin-bottom: 12px;
}
.markdown-body :deep(p) {
  margin-bottom: 16px;
  font-size: 22px;
}
.markdown-body :deep(ul), .markdown-body :deep(ol) {
  padding-left: 2em;
  margin-bottom: 16px;
}
.markdown-body :deep(li) {
  margin-bottom: 0.5em;
  font-size: 20px;
}
.markdown-body :deep(code) {
  background-color: #f6f8fa;
  border-radius: 3px;
  padding: 0.2em 0.4em;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier,
    monospace;
}
.markdown-body :deep(pre) {
  background-color: #f6f8fa;
  border-radius: 3px;
  padding: 16px;
  overflow: auto;
}
.markdown-body :deep(pre code) {
  padding: 0;
  background-color: transparent;
}
.markdown-body :deep(strong) {
  font-weight: 600;
}
.markdown-body :deep(blockquote) {
  color: #6a737d;
  border-left: 0.25em solid #dfe2e5;
  padding: 0 1em;
  margin-left: 0;
}
.markdown-body :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin-top: 16px;
  margin-bottom: 16px;
}
.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid #dfe2e5;
  padding: 12px 15px;
  text-align: left;
}
.markdown-body :deep(th) {
  background-color: #f6f8fa;
  font-weight: 600;
}
</style> 