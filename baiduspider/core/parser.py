import json
from html import unescape

from bs4 import BeautifulSoup

from baiduspider.core._spider import BaseSpider
from baiduspider.errors import ParseError


class Parser(BaseSpider):
    def __init__(self) -> None:
        super().__init__()

    def parse_web(self, content: str) -> dict:
        """解析百度网页搜索的页面源代码

        Args:
            content (str): 已经转换为UTF-8编码的百度网页搜索HTML源码

        Returns:
            dict: 解析后的结果
        """
        soup = BeautifulSoup(self._minify(content), 'html.parser')
        # 尝试获取搜索结果总数
        try:
            num = int(str(soup.find('span', class_='nums_text').text).strip(
                '百度为您找到相关结果约').strip('个').replace(',', ''))
        except:
            num = 0
        # 查找运算窗口
        calc = soup.find('div', class_='op_new_cal_screen')
        # 定义预结果（运算以及相关搜索）
        pre_results = []
        # 预处理相关搜索
        try:
            _related = soup.find('div', id='rs').find('table').find_all('th')
        except:
            _related = []
        related = []
        # 预处理新闻
        news = soup.find('div', class_='result-op',
                         tpl='sp_realtime_bigpic5', srcid='19')
        # 确认是否有新闻块
        try:
            news_title = self._format(
                news.find('h3', class_='t').find('a').text)
        except:
            news_title = None
            news_detail = []
        else:
            news_rows = news.findAll('div', class_='c-row')
            news_detail = []
            for row in news_rows:
                row_title = self._format(row.find('a').text)
                row_time = self._format(
                    row.find('span', style='color:#666;float:right').text)
                row_author = self._format(
                    row.find('span', style='color:#008000').text)
                row_url = self._format(row.find('a')['href'])
                news_detail.append({
                    'title': row_title,
                    'time': row_time,
                    'author': row_author,
                    'url': row_url
                })
        # 预处理短视频
        video = soup.find('div', class_='op-short-video-pc')
        if video:
            video_rows = video.findAll('div', class_='c-row')
            video_results = []
            for row in video_rows:
                row_res = []
                videos = row.findAll('div', class_='c-span6')
                for v in videos:
                    v_link = v.find('a')
                    v_title = v_link['title']
                    v_url = self._format(v_link['href'])
                    v_img = v_link.find('img')['src']
                    v_len = self._format(
                        v.find('div', class_='op-short-video-pc-duration-wrap').text)
                    v_from = self._format(
                        v.find('div', class_='op-short-video-pc-clamp1').text)
                    row_res.append({
                        'title': v_title,
                        'url': v_url,
                        'cover': v_img,
                        'length': v_len,
                        'origin': v_from
                    })
                video_results += row_res
        else:
            video_results = []
        # 一个一个append相关搜索
        for _ in _related:
            if _.text:
                related.append(_.text)
        # 预处理百科
        baike = soup.find('div', class_='c-container', tpl='bk_polysemy')
        if baike:
            b_title = self._format(baike.find('h3').text)
            b_url = baike.find('a')['href']
            b_des = self._format(baike.find(
                'div', class_='c-span-last').find('p').text)
            try:
                b_cover = baike.find(
                    'div', class_='c-span6').find('img')['src']
                b_cover_type = 'image'
            except (TypeError, AttributeError):
                try:
                    b_cover = baike.find(
                        'video', class_='op-bk-polysemy-video')['data-src']
                    b_cover_type = 'video'
                except TypeError:
                    b_cover = None
                    b_cover_type = None
            baike = {
                'title': b_title,
                'url': b_url,
                'des': b_des,
                'cover': b_cover,
                'cover-type': b_cover_type
            }
        # 加载搜索结果总数
        if num != 0:
            pre_results.append(dict(type='total', result=num))
        # 加载运算
        if calc:
            pre_results.append(dict(type='calc', process=str(calc.find('p', class_='op_new_val_screen_process').find(
                'span').text), result=str(calc.find('p', class_='op_new_val_screen_result').find('span').text)))
        # 加载相关搜索
        if related:
            pre_results.append(dict(type='related', results=related))
        # 加载资讯
        if news_detail:
            pre_results.append(dict(type='news', results=news_detail))
        # 加载短视频
        if video_results:
            pre_results.append(dict(type='video', results=video_results))
        # 加载百科
        if baike:
            pre_results.append(dict(type='baike', result=baike))
        # 预处理源码
        error = False
        try:
            soup = BeautifulSoup(self._minify(
                str(soup.findAll(id='content_left')[0])), 'html.parser')
        # 错误处理
        except IndexError:
            error = True
        finally:
            if error:
                raise ParseError(
                    'Failed to generate BeautifulSoup object for the given source code content.')
        results = BeautifulSoup(self._minify(
            str(soup)), 'html.parser').findAll(class_='c-container')
        res = []
        for result in results:
            des = None
            soup = BeautifulSoup(self._minify(str(
                result)), 'html.parser')
            # 链接
            href = soup.find_all('a', target='_blank')[0].get('href').strip()
            # 标题
            title = self._format(
                str(soup.find_all('a', target='_blank')[0].text))
            # 时间
            try:
                time = self._format(soup.find_all(
                    'div', class_='c-abstract')[0].find('span', class_='newTimeFactor_before_abs').text)
            except (AttributeError, IndexError):
                time = None
            try:
                # 简介
                des = soup.find_all('div', class_='c-abstract')[0].text
                soup = BeautifulSoup(str(result), 'html.parser')
                des = self._format(des).lstrip(str(time)).strip()
            except IndexError:
                try:
                    des = des.replace('mn', '')
                except (UnboundLocalError, AttributeError):
                    des = None
            if time:
                time = time.split('-')[0].strip()
            # 因为百度的链接是加密的了，所以需要一个一个去访问
            # 由于性能原因，分析链接部分暂略
            # if href is not None:
            #     try:
            #         # 由于性能原因，这里设置1秒超时
            #         r = requests.get(href, timeout=1)
            #         href = r.url
            #     except:
            #         # 获取网页失败，默认换回原加密链接
            #         href = href
            #     # 分析链接
            #     if href:
            #         parse = urlparse(href)
            #         domain = parse.netloc
            #         prepath = parse.path.split('/')
            #         path = []
            #         for loc in prepath:
            #             if loc != '':
            #                 path.append(loc)
            #     else:
            #         domain = None
            #         path = None
            try:
                is_not_special = result['tpl'] not in [
                    'short_video_pc', 'sp_realtime_bigpic5', 'bk_polysemy']
            except KeyError:
                is_not_special = False
            if is_not_special:  # 确保不是特殊类型的结果
                # 获取可见的域名
                try:
                    domain = result.find('div', class_='c-row').find('div', class_='c-span-last').find(
                        'div', class_='se_st_footer').find('a', class_='c-showurl').text
                except Exception as error:
                    try:
                        domain = result.find(
                            'div', class_='c-row').find('div', class_='c-span-last').find('p', class_='op-bk-polysemy-move').find('span', class_='c-showurl').text
                    except Exception as error:
                        try:
                            domain = result.find(
                                'div', class_='se_st_footer').find('a', class_='c-showurl').text
                        except:
                            domain = None
                if domain:
                    domain = domain.replace(' ', '')
            else:
                domain = None
            # 加入结果
            if title and href and is_not_special:
                res.append({
                    'title': title,
                    'des': des,
                    'origin': domain,
                    'url': href,
                    'time': time,
                    'type': 'result'})
        soup = BeautifulSoup(content, 'html.parser')
        soup = BeautifulSoup(str(soup.findAll('div', id='page')
                                 [0]), 'html.parser')
        # 分页
        pages_ = soup.findAll('span', class_='pc')
        pages = []
        for _ in pages_:
            pages.append(int(_.text))
        # 如果搜索结果仅有一页时，百度不会显示底部导航栏
        # 所以这里直接设置成1，如果不设会报错`TypeError`
        if not pages:
            pages = [1]
        # 设置最终结果
        result = pre_results
        result.extend(res)
        return {
            'results': result,
            # 最大页数
            'pages': max(pages)
        }

    def parse_pic(self, content: str) -> dict:
        """解析百度图片搜索的页面源代码

        Args:
            content (str): 已经转换为UTF-8编码的百度图片搜索HTML源码

        Returns:
            dict: 解析后的结果
        """
        # 从JavaScript中加载数据
        # 因为JavaScript很像JSON（JavaScript Object Notation），所以直接用json加载就行了
        # 还有要预处理一下，把函数和无用的括号过滤掉
        error = None
        try:
            data = json.loads(content.split('flip.setData(\'imgData\', ')[1].split(
                'flip.setData(')[0].split(']);')[0].replace(');', '').replace('<\\/strong>', '</strong>').replace('\\\'', '\''))
        except Exception as err:
            error = err
        finally:
            if error: raise ParseError(str(error))
            del error
        results = []
        for _ in data['data'][:-1]:
            if _:
                # 标题
                title = str(_['fromPageTitle']).encode('utf-8').decode('utf-8')
                # 去除标题里的HTML
                title = unescape(self._remove_html(title))
                # 链接
                url = _['objURL']
                # 来源域名
                host = _['fromURLHost']
                # 生成结果
                result = {
                    'title': title,
                    'url': url,
                    'host': host
                }
                results.append(result)  # 加入结果
        # 获取分页
        bs = BeautifulSoup(content, 'html.parser')
        pages_ = bs.find('div', id='page').findAll('span', class_='pc')
        pages = []
        for _ in pages_:
            pages.append(int(_.text))
        return {
            'results': results,
            # 取最大页码
            'pages': max(pages)
        }
